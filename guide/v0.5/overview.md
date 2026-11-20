# Overview

A crocket program is a set of functions, a few calls that mount them, and whatever state and fairings you attach. This page is the map. The later chapters are the detail.

## A handler is a function

```cpp
namespace api {

[[= http::get("/hello/{name}/{age}")]]
auto hello(std::string_view name, std::uint8_t age) -> std::string {
  return std::format("Hello, {} year old named {}!", age, name);
}

auto helper(int) -> int;  // no annotation: not a route

}  // namespace api
```

`{name}` binds to the parameter named `name`. A name or type mismatch is a compile error that names both identifiers. Parameters that are not in the path are extractors. An unknown parameter type does not compile. The return type has to be a responder, or an awaitable of one (`Task<T>`).

One route annotation per function. Two verbs are two functions. Handlers are not templates, because reflection needs concrete parameter types.

## Mounting

```cpp
return crocket::build(Config::from_env())
    .attach(Logger{})
    .mount("/", reflect_routes<^^api>())
    .launch();
```

`reflect_routes<^^api>()` reads every annotated function in that namespace or class. The string you pass to `mount` is the URL prefix for HTTP routes. Routes are compiled at ignite into a tree keyed by path segment, so finding candidates takes the same time with 10 routes or 1,000, and the lookup allocates nothing. A route may have up to 64 segments and 16 captures.

A class can be a route scope too. Static members are ordinary handlers. Non-static members run on the instance you `manage`, and ignite checks that you did.

```cpp
class Info {
 public:
  explicit Info(std::string version) : version_(std::move(version)) {}

  [[= http::get("/version")]]
  auto version() const -> std::string { return version_; }

 private:
  std::string version_;
};

app.manage(Info{"1.4.2"}).mount("/", reflect_routes<^^Info>());
```

## If you know Rocket

| Rocket | crocket |
|---|---|
| `#[get("/hello/<name>/<age>")]` | `[[= http::get("/hello/{name}/{age}")]]` |
| `routes![a, b, c]` | `reflect_routes<^^api>()` |
| `rocket::build().mount("/", ...)` | `crocket::build().mount("/", ...)` |
| `FromParam` | `crocket::FromParam<T>` |
| Request guards | Extractors, `crocket::FromRequest<T>` |
| `Json<T>` | `Json<T>` |
| Query / `FromForm` for queries | `Query<T>` |
| `Responder` | `crocket::Responder<T>` |
| `Option`, `Result`, `status::Created` | `std::optional`, `std::expected`, `Created<T>` |
| `.manage(x)` and `&State<T>` | `.manage(x)` and `State<T>` |
| Fairings | Fairings, same hook names, as plain structs |
| `async fn` | Handlers that return `Task<T>` |
| `rocket::local::blocking::Client` | `LocalClient` |

Four things crocket adds that Rocket has no direct equivalent for: controllers, OpenAPI generated from the handlers, unary gRPC whose messages are plain structs, and a production kit (request ids, structured logs, Prometheus metrics, `/healthz` and `/readyz`, deadlines, resource pools).

HTML form bodies and multipart uploads are not a separate `FromForm` type. Query strings are `Query<T>`.

## Where a handler runs

Network I/O runs on one event loop per physical core. Hyperthreads of a core don't get a loop each. A plain function starts on a worker thread, so it may block. A handler that returns `Task<T>` runs on the event loop and must not block.

Adaptive placement is on by default. A plain route moves onto the event loops after 1,000 runs in a row under 100 microseconds, and back to workers when it turns out to block there (one run over 50 ms, or 8 over 1 ms within a second). `CROCKET_ADAPTIVE_PLACEMENT=false` keeps plain functions on workers.

## When things fail

- At compile time, when the types say so: a capture with no matching parameter, an unknown extractor, a return type that is not a responder.
- At ignite, before the server accepts a connection: unmanaged state, two routes with the same method, shape, and rank, a fairing that calls `ig.fail`, a bad proxy list.
- At `launch`, TLS certificate and key files must exist and be readable.
- On the request, when a value doesn't fit: 404 `path.invalid`, 422 from JSON or query, 401 from auth. The handler does not run.

Every problem ignite can see is reported at once, not just the first.
