# Requests

A route runs only when the method, the path, and every extractor succeed. This chapter is that matching.

## Routes and captures

```cpp
[[= http::get("/hello/{name}/{age}")]]
auto hello(std::string_view name, std::uint8_t age) -> std::string {
  return std::format("Hello, {} year old named {}!", age, name);
}
```

Each `{capture}` binds to the parameter with the same name. The parameter's type decides whether the segment is acceptable. Built-in path types are `std::string_view`, `std::string`, `bool`, the integer types (range-checked), and the floating-point types. A floating-point capture has to be finite: `nan` and `inf` don't match.

Paths are split on `/` before they are decoded, so a capture can hold any character. `/hello/a%2Fb/36` calls `hello` with `name` equal to `a/b`. Dot segments are removed first and never climb above `/`. A path that decodes to a NUL byte is 400.

A capture that doesn't match a parameter is a compile error:

```text
error: static assertion failed: crocket: handler bad::hello [GET /hello/{name}/{age}]:
  path capture '{age}' has no parameter named 'age'; did you mean parameter 'years'?
```

Add your own path type by specializing `FromParam`. `parse` returns `std::nullopt` when the segment doesn't match, and the route is forwarded.

```cpp
struct Hex { std::uint32_t value; };

template <>
struct crocket::FromParam<Hex> {
  static auto parse(std::string_view s) -> std::optional<Hex> {
    std::uint32_t v{};
    auto [p, ec] = std::from_chars(s.data(), s.data() + s.size(), v, 16);
    if (s.empty() || ec != std::errc{} || p != s.data() + s.size()) return std::nullopt;
    return Hex{v};
  }
};
```

## Forwarding and ranks

A path that fails to parse doesn't stop routing. The request is forwarded to the next candidate. Candidates are tried in this order: lower `rank` first, then literal segments before captures, then mount order. If every candidate forwards, the response is 404 `path.invalid`.

```cpp
[[= http::get("/user/{id}", {.rank = 1})]]
auto user_by_id(std::uint64_t id) -> std::string;

[[= http::get("/user/{name}", {.rank = 2})]]
auto user_by_name(std::string_view name) -> std::string;
```

`/user/42` hits the first. `/user/ada` doesn't parse as an integer, so it hits the second. Two routes with the same method, path shape, and rank fail at ignite, with both handlers named.

## Methods

The annotations are `http::get`, `head`, `post`, `put`, `patch`, `del`, and `options`.

HEAD falls back to the GET route and drops the body. A method that doesn't match a path that does exist gets 405 with an `Allow` header.

## Extractors

Every parameter that isn't a path capture is an extractor. Extractors run before the handler. If one fails, its `ApiError` is the response.

| Extractor | Gives you | Fails with |
|---|---|---|
| `Json<T>` | Body decoded into `T` | 415, or 422 `json.invalid` and the other `json.*` codes |
| `Query<T>` | Query string mapped onto `T` | 422 `query.invalid` |
| `Header<"name", T>` | That header, parsed as `T` | 400 `header.missing` or `header.invalid` |
| `Auth<>` / `Auth<T>` | A verified bearer token | 401, or 403 `auth.forbidden` |
| `State<T>` | The managed `T` | Checked at ignite, not per request |
| `Deadline` | A deadline and a `std::stop_token` | Never |
| `RequestId` | The request's id | Never |
| `Client` | Address and scheme | Never |
| `const Request&` / `Response&` | The raw objects | Never |

A custom guard is a `FromRequest` specialization. A parameter type that is neither a path type nor an extractor is a compile error. So is a handler with two body-consuming extractors.

Failures are counted per route and extractor kind in `crocket_extractor_failures_total{route,kind}` when metrics are attached.

## JSON

Any plain aggregate works as JSON. No annotations are required.

```cpp
struct NewUser {
  std::string email;                // required
  std::optional<std::string> name;  // may be absent or null
  int age = 0;                      // may be absent: keeps its default
};

[[= http::post("/users")]]
auto create(Json<NewUser> body) -> Json<NewUser> { return body; }
```

By default, JSON names are the member names. A member is required unless it is `optional` or has a default. Unknown fields are ignored. Empty optionals are written as `null`. `Json<T>` reads the body straight into `T`, with no document tree in between.

Reading is strict. UTF-8 is checked. Duplicate keys are 422 `json.duplicate_key`, including keys a struct ignores. Nesting is limited to 64, strings to 1 MiB, object members to 1024, and array elements to 100,000. An integer that doesn't fit the member's type is an error, not a rounded number. `std::uint64_t` keeps all 64 bits.

Annotations change the defaults when you need them: `json::rename`, `json::rename_all`, `json::deny_unknown_fields`, `json::omit_null`, `json::as_string`, `json::unix_seconds`, `json::unix_millis`, and `json::tag` for a variant. Validation annotations (`json::email`, `json::min`, `json::max`, `json::min_len`, `json::max_len`, `json::pattern`) collect every failure into one 422 `json.validation`. `json::pattern` is compiled with the program, matches in linear time, and has no backreferences or lookaround.

`[[= json::from_path]]` on a member fills it from the URL instead of the body, so one struct can serve create and update. The id is `readOnly` in OpenAPI.

Outside a handler, `json::read`, `json::from_string<T>`, `json::to_string`, and `json::parse` do the same mapping.

## Queries and headers

```cpp
struct Page { int page = 1; std::optional<std::string> q; };

[[= http::get("/search")]]
auto search(Query<Page> p) -> std::string {
  return std::format("page {} of results for {}", p->page, p->q.value_or("*"));
}

[[= http::get("/reports")]]
auto reports(Header<"x-tenant"> tenant,
             Header<"x-page-size", std::optional<int>> size) -> std::string {
  return std::format("{} {}", *tenant, size->value_or(50));
}
```

`/search?page=2&q=rust` maps onto `Page`. A required header that is missing is 400 `header.missing`. Every request header reaches the handler, over HTTP/1.1 and HTTP/2.

## Authentication

JWT and OIDC are optional. Link `crocket::auth` (it also links `crocket::client`, which fetches JWKS) and manage one `auth::Jwt`. `#include <crocket/auth.hpp>` is not pulled in by `crocket.hpp`.

```cpp
[[= http::get("/admin"), = auth::require("admin")]]
auto admin() -> std::string { return "admin\n"; }

return build(Config::from_env())
    .manage(auth::Jwt::from_env())
    .mount("/", reflect_routes<^^api>())
    .launch();
```

`Auth<>` is the untyped principal: `subject` and `scopes`. `Auth<T>` also fills `T` from the payload the way `Json<T>` reads a body. A missing or invalid token is 401. A valid token without the required role is 403 `auth.forbidden`. `auth::require` means every role. `auth::any_of` means one of them.

The default algorithms are RS256, ES256, and EdDSA. `none` is rejected. HS256, HS384, and HS512 stay off unless you set `CROCKET_AUTH_SECRET` and include the algorithm. `Jwt::from_env` adds HS256 when the secret is set. An HMAC key is only that secret. A JWK is never used as an HMAC key.

`/readyz` stays not ready until the first JWKS document has loaded. A later failed refresh keeps the keys already in memory. There is no introspection, so a token revoked at the issuer stays accepted until it expires. Verified tokens are cached on each worker until `exp` (1,024 entries).

`CROCKET_AUTH=ON` fails configure when the client is off. With both options left on `AUTO`, turning the client off turns auth off.
