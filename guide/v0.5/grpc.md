# gRPC

Unary gRPC methods are functions. Messages are plain structs, encoded as proto3 by reflection. There is no `.proto` to keep in sync and no generated code. Streaming is not supported.

## A method

```cpp
struct HelloRequest {
  std::string name;                                     // field 1
  std::optional<std::string> title;                     // field 2
  [[= proto::field(4)]] std::vector<std::string> tags;  // field 4 (3 was retired)
};
struct HelloReply { std::string message; };

namespace greeter {

[[= grpc::rpc]]
auto say_hello(HelloRequest req, Auth<> auth) -> Result<HelloReply> {
  if (req.name.empty())
    return std::unexpected(ApiError::bad_request("hello.name", "name is required"));
  return HelloReply{"Hello, " + req.name};
}

}  // namespace greeter

crocket::build()
    .mount("helloworld", reflect_routes<^^greeter>(), Mode::Grpc)
    .mount("/api", reflect_routes<^^api>())
    .launch({.port = 50051, .h2_prior_knowledge = true});
```

`Mode::Grpc` makes the first argument of `mount` a protobuf package (`"helloworld"`, `"acme.v1"`, or `""`) instead of a URL prefix. The service is the namespace or class and the method is the function, both in PascalCase. `greeter::say_hello` is `POST /helloworld.Greeter/SayHello`. Mounting gRPC methods without `Mode::Grpc`, or HTTP routes with it, fails ignite.

Field numbers follow declaration order from 1. `[[= proto::field(n)]]` pins a member, and the members after it continue from `n + 1`. Duplicate or reserved numbers are compile errors. Pin numbers before you reorder or remove members, because renumbering breaks existing clients.

The types are `bool`, `intN_t`, `uintN_t`, `float`, `double`, `std::string`, `proto::Bytes`, enums, nested structs, and `std::optional`, `std::vector`, and `std::map` of those. Unknown fields are skipped when decoding.

A method takes at most one request message. None means `google.protobuf.Empty`. It can also take any extractor that does not read the body: `Auth<>`, `State<T>`, `Deadline`, `Header<...>`. Custom metadata arrives as request headers, so `Header<"x-tenant">` reads it.

You can return a message, `Result<T>`, `std::optional<T>` (empty is `NOT_FOUND`), `void` (`Empty`), or a `Task` of one of those.

## Errors and deadlines

An `ApiError` becomes a gRPC status derived from its HTTP status: 401 `UNAUTHENTICATED`, 404 `NOT_FOUND`, 422 `INVALID_ARGUMENT`, 504 `DEADLINE_EXCEEDED`, and so on. `message` goes in `grpc-message`. The dotted code goes in a `crocket-error-code` trailer. `grpc::error(grpc::Code::AlreadyExists, "user.exists", "...")` picks the code exactly. An unknown method is `UNIMPLEMENTED`.

A `grpc-timeout` header can shorten `timeouts.request`. It cannot extend it.

## HTTP/2

gRPC needs HTTP/2. Over TLS it is negotiated with ALPN. A gRPC client on an insecure channel speaks h2 without TLS, which `h2_prior_knowledge` serves. The same port keeps serving HTTP/1.1. `CROCKET_H2_PRIOR_KNOWLEDGE=true` sets the flag without a code change. `examples/grpc.cpp` turns it on when no TLS certificate is configured, and defaults the port to 50051 through `Config::from_env`.

## The .proto

Other languages still want a schema. It comes from the same declarations:

```cpp
std::fputs(grpc::proto_file<^^greeter>("helloworld").c_str(), stdout);
```

That prints a `service Greeter` block and every message and enum the methods use. Enum values get their enum's prefix, as proto3 requires (`Mood::grumpy` is `MOOD_GRUMPY`). A missing zero value is added as `<ENUM>_UNSPECIFIED`. `crocket_grpc --proto` prints the schema for `examples/grpc.cpp`.

To test without sockets, `LocalClient::grpc` sends one framed message and `grpc::read_reply<T>` decodes the answer.

```cpp
auto res = client.grpc("/helloworld.Greeter/SayHello",
                       proto::encode(HelloRequest{.name = "Ada"}))
               .dispatch();
assert(grpc::read_reply<HelloReply>(res)->message == "Hello, Ada");
```
