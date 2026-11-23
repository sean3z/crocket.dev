# Responses

The return type is the response. crocket maps a fixed set of types. Anything else is a compile error unless you specialize `Responder`.

## Return types

| You return | The client gets |
|---|---|
| `std::string`, `std::string_view`, `const char*` | 200, `text/plain; charset=utf-8` |
| A plain struct, `Json<T>`, `std::vector<T>` | 200, `application/json` |
| `std::optional<T>` | 200, or 404 when it is empty |
| `std::expected<T, ApiError>` (`Result<T>`) | The value, or that error |
| `Created<T>` | 201, with `Location` when you set one |
| `NoContent` | 204, empty body |
| `Cacheable<T>` | The payload, plus validators and optional ranges |
| `Task<T>` | Whatever `T` is, after the task finishes |
| `Response` | Exactly what you built |

```cpp
[[= http::post("/heroes")]]
auto create(Db& db, Json<Hero> body) -> Created<Hero> {
  auto hero = db.insert(*body);
  return {hero, "/heroes/" + std::to_string(hero.id)};
}
```

An empty `optional` is a 404. You don't write the status yourself. `Status<T>` sets a status code on a successful payload when none of the wrappers fit.

## Errors

Error bodies are RFC 9457 problem details (`application/problem+json`): `title`, `status`, `detail`, `code`, `request_id`, and `errors` when a validation failure has per-field notes.

```json
{"title":"Unprocessable Content","status":422,
 "detail":"field '/email': must be an email address",
 "code":"json.validation","request_id":"5f0c"}
```

Codes are stable and dotted: `path.invalid`, `query.invalid`, `json.invalid`, `auth.expired`, `body.too_large`. An uncaught exception is 500 `internal`. Its `what()` never reaches the client, except in the dev profile, where `ApiError::detail` is included.

Return `std::unexpected(ApiError::bad_request("hello.name", "name is required"))` when the handler wants a specific code. The status, the message, and the code are the whole error.

## Caching and ranges

Every 200 answer to GET or HEAD carries an ETag, a hash of the body, unless the handler set its own. Bodies longer than `limits.etag_max_bytes` (1 MiB) get no automatic ETag. Hashing is about a microsecond per 10 KiB. A client that sends the tag back in `If-None-Match` gets 304 with no body.

Wrap the payload in `Cacheable` for the rest:

```cpp
[[= http::get("/reports/{id}")]]
auto report(std::uint64_t id, State<Store> store) -> Cacheable<std::string> {
  auto r = store->find(id);
  return {r.contents, {.last_modified = r.updated_at, .ranges = true}};
}
```

`last_modified` is sent as `Last-Modified` and answers `If-Modified-Since`. When the client sends `If-None-Match`, that decides instead. `ranges = true` serves one byte range as 206. A range past the end is 416 `range.unsatisfiable`. Several ranges in one request get the whole body.

## Static files

`.mount(prefix, files{...})` serves a directory, or bytes embedded with `#embed`, under that URL prefix. Routes match before files, whichever you mount first, so a handler never waits on the filesystem. A miss is the ordinary 404. That is how `/` can serve a frontend next to an API without swallowing `/healthz`.


A directory on disk is the shortest version. `root` is opened once at ignite, and every request reads relative to it:

```cpp
.mount("/", files{
    .root = "public",
    .precompressed = true,
    .cache = {{"*.html", "no-cache"},
              {"assets/*", "public, max-age=31536000, immutable"}}})
```

`precompressed` serves a sibling `app.js.br` or `app.js.gz` when the client accepts it, so you compress once at build time. Edits to a file show up without a restart.

Embedding puts the frontend inside the binary instead, so there's nothing to copy next to it when you ship:

```cpp
static constexpr unsigned char index_html[] = {
#embed "web/index.html"
};

.mount("/", files{
    .assets = {asset("index.html", index_html)},
    .cache = {{"*.html", "no-cache"}},
    .headers = {{"*.html", {{"content-security-policy",
                             "default-src 'self'"}}}}})
```

`asset()` points at the array. A string literal's trailing NUL would be part of the file, so embed the file rather than quoting it. Only GET and HEAD read files.

A few fields you'll use immediately:

- `index` defaults to `index.html`. A directory URL that ends in `/` serves it. Without the slash the response is 308 to the path with a slash.
- `*` in a cache or header glob matches any run of characters except `/`. `*.html` matches `index.html` and not `dir/index.html`. The first matching rule wins.
- `.headers` replaces a header Shield would have set, for files that match the glob. Shield's default content security policy is `default-src 'none'`, which blocks a page from loading its own scripts and styles. Set a policy the page can live with.
- Dotfiles are hidden unless `.dotfiles` is set. A symlink is followed only when the target stays inside the root. `%2e%2e%2f` is a miss.
- `max_bytes` defaults to 32 MiB. A larger file on disk is 500 `static.too_large`. A larger embedded asset fails ignite.
- `.spa` serves the index for a GET or HEAD that missed and whose last segment has no dot. A missing `app.js` stays a 404. Routes, including `/healthz`, still win.

Embedded files send a strong ETag and no `Last-Modified`. Disk files send an ETag of size and mtime, and `Last-Modified`. `If-None-Match` and `If-Modified-Since` answer 304. One `Range` is 206. `HEAD` never sends a body.

h2o's own file handler is not used. It can't serve embedded bytes, and that code stays out of the binary.
