# Testing

Handlers are plain functions, so you can call them directly. `LocalClient` is how you test the pipeline around them without opening a socket.

## LocalClient

`LocalClient` dispatches through fairings, routing, extractors, responders, and error mapping. It plays the role of Rocket's `local::blocking::Client`. It normalizes and routes paths the same way the server does, so an in-process test cannot pass on an input the server treats differently.

```cpp
Crocket app = make_app();
LocalClient client(app);

auto res = client.post("/users").bearer("alice").json(R"({"email":"a@example.com"})").dispatch();
assert(res.status == 201);
assert(*res.headers.get("location") == "/users/1");

auto bad = client.get("/hello/Ada/400").dispatch();
assert(bad.status == 404 && bad.error_code == "path.invalid");
```

Construction ignites the app and throws if ignite fails. `.remote("10.0.0.5")` sets the peer, which is how you test trusted proxies:

```cpp
auto r = client.get("/whoami")
             .remote("10.0.0.5")
             .header("x-forwarded-for", "203.0.113.9")
             .dispatch();
```

Only a peer in `proxy.trusted` is believed. A request from any other address keeps its own address and scheme, whatever headers it sends.

`tests/acceptance.cpp` is the larger example: routing, responders, request ids, logs, metrics, health checks, CORS, pools, the dev profile, Shield, ETags, 304s, and ranges.

## Compile failures

`tests/compile_fail/` holds programs that must not compile. Each one is checked for the expected diagnostic. That includes the `{age}` versus `years` error, which has to name both identifiers, plus unknown extractors, bad JSON annotations, and return types that are not responders. A control file in the same directory must compile.

## What else the suite covers

You don't need these to test an application. They're how crocket itself is checked, and they're the contract behind the chapters in this guide.

- `json` covers round trips, limits, duplicate keys, and validation.
- `router` checks the route tree against a linear scan, including HEAD falling back to GET.
- `static` covers directories, `#embed`, index files, dotfiles, and symlink misses.
- `tls_h2` drives real sockets with ALPN h2 and HTTP/1.1.
- `openapi` checks the generated document piece by piece.
- `grpc` checks protobuf encoding and the generated `.proto`.
- `db` runs against Postgres when `CROCKET_TEST_DATABASE_URL` is set, and is skipped otherwise.

`ctest` also runs each fuzz target's corpus and two seconds of mutations. The fuzzers cover JSON, protobuf, query strings, routes, whole requests, and HTTP/2 frames.
