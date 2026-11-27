# Introduction

crocket is a C++ web framework in the same spirit as [Rocket](https://rocket.rs). It's not a port. Handlers are functions. Path captures and extractors are arguments. The return value is the response. You declare a route with a C++26 annotation, and `reflect_routes` discovers it. The wire layer is [h2o](https://github.com/h2o/h2o): HTTP/1.1, HTTP/2, and TLS.

This guide describes that model. The code samples match the [@release@](https://github.com/sean3z/crocket/releases/tag/@release@) release, which is the tree this site was checked against.

## What you write

A route is an ordinary function with one route annotation. Mounting a namespace picks up every annotated function in it. Helpers with no annotation stay helpers.

```cpp
namespace api {

[[= http::get("/hello/{name}/{age}")]]
auto hello(std::string_view name, std::uint8_t age) -> std::string {
  return std::format("Hello, {} year old named {}!", age, name);
}

}  // namespace api

crocket::build()
    .attach(Logger{})
    .mount("/", reflect_routes<^^api>())
    .launch({.listen = "0.0.0.0:8000"});
```

`/hello/Ada/36` calls `hello`. `/hello/Ada/400` does not, because 400 is not a `uint8_t`. The response is 404 `path.invalid`, and the handler never runs.

## Why reflection

Most C++ web frameworks bind routes with a runtime registration call, a macro, or a code generator. crocket uses C++26 static reflection instead. `reflect_routes<^^api>()` reads the functions, their annotations, and their parameter names at compile time.

- Nothing to register. You can't forget to add a route to a list, because there isn't a list.
- A mismatch is a compile error that names both identifiers. Reflection can see parameter names, which templates alone cannot.
- Reflection runs only in the compiler. Each route becomes a function pointer. A request does not pay for a string lookup, RTTI, or type erasure per argument.
- The same signatures and structs produce the JSON mapping, the OpenAPI document, and, for gRPC, the `.proto`.

The trade-off is the toolchain. You need a compiler with C++26 reflection. crocket is developed on GCC 16.2 with `-freflection`. See [Getting started](/guide/v0.5/getting-started/).

## Goals

These are the rules the framework is built around.

1. A handler is a function. `{id}` in the path is a parameter named `id`. `Json<T>`, `Auth`, and `State<T>` are more parameters. The return type is the response.
2. Route metadata lives on the function. You mount a namespace or a controller class, not a handwritten list.
3. Cross-cutting behavior belongs to the application. `attach` adds fairings. `manage` adds typed singletons.
4. Production behavior is built in: request ids, structured errors, deadlines, readiness, limits, ignite checks, and a drain on shutdown. Logging and metrics are there when you attach them.
5. One wire engine, h2o. Handlers never include h2o headers.

## Non-goals

crocket is not an ORM and not a plugin ABI. It does not reload application code without a restart. Reloading a TLS certificate is supported, because that is configuration. It does not discover routes by scanning a whole translation unit. It does not do reflection, string lookups, or type erasure per argument on the request path.

WebSockets, server-sent events, and streamed bodies are not built. What's planned on the way to 1.0 is tracked in [issue 37](https://github.com/sean3z/crocket/issues/37).

## Where to go next

If you want a running process as fast as possible, start with the [quickstart](/guide/v0.5/quickstart/). The [overview](/guide/v0.5/overview/) is the map of the rest of the guide. If you're coming from Node, read [Migrating from Express](/guide/v0.5/migrate-express/). If you're coming from Java, read [Migrating from Spring Boot](/guide/v0.5/migrate-spring/).
