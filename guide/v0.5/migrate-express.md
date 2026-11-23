# Migrating from Express

You already know the shape: a function per route, a bit of middleware, `listen` at the bottom. crocket is that shape in C++. The handler is still a function. The arguments are the path, the query, and the JSON body. The return value is the response.

The Express examples here are Express 5.

The crocket column on this page is written against the [0.5.2](https://github.com/sean3z/crocket/releases/tag/0.5.2) release, which is the tree this site is pinned to. The same program is the [Spring Boot](/guide/v0.5/migrate-spring/) column's crocket side.

Every success response below is the same JSON. `POST /users` with `{"email":"ada@example.com","name":"Ada"}` answers 201, `Location: /users/1`, and `{"id":1,"email":"ada@example.com","name":"Ada"}`.

## Project and build

Express installs a package and starts a script. crocket is a library you compile in. You need GCC 16.2. Linking `crocket::crocket` turns on `-freflection`, so the target doesn't set the standard itself. `crocket::auth` is only there for the JWT route.

:::pair Express | crocket

```json
{
  "name": "users",
  "type": "module",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^5.1.0"
  }
}
```

```sh
npm install
npm start
```

|

```cmake
cmake_minimum_required(VERSION 3.28)
project(users CXX)

include(FetchContent)
FetchContent_Declare(crocket
  GIT_REPOSITORY https://github.com/sean3z/crocket.git
  GIT_TAG 0.5.2)
FetchContent_MakeAvailable(crocket)

add_executable(users users.cpp)
target_link_libraries(users PRIVATE
  crocket::crocket crocket::auth)
```

```sh
cmake -S . -B build
cmake --build build
```

:::

`npm start` runs `node server.js`, the listen example below. The binary is `build/users`.

## Listen

Express binds a port when you call `listen`. crocket builds an app from `Config::from_env()` and binds it when you call `launch`. The default port is 8000. The environment can replace it, and the variable names are in the [configuration](/guide/v0.5/configuration/) chapter.

:::pair Express | crocket

```js
import express from "express";

export const app = express();
app.use(express.json());

const port = Number(process.env.PORT ?? 8080);
app.listen(port);
```

```cpp
auto main() -> int {
  return build(Config::from_env())
      .launch();
}
```

:::

`launch` serves until the process is signaled. There's no callback after listen. `GET /healthz` is already registered and answers `{"status":"ok"}`. The routes below mount onto that same builder. The program sets the port to 8080 so the rest of this page matches the Express and Spring examples.

## Path parameters

`req.params.id` is a string. In crocket the `{id}` capture has to be a parameter named `id`, and the type is checked before your function runs. `GET /users/nope` matches the route, the capture doesn't parse, and `user_by_id` doesn't run. The body is 404 `path.invalid` with detail `not found`.

:::pair Express | crocket

```js
app.get("/users/:id", (req, res) => {
  const id = Number(req.params.id);
  if (id !== 1) {
    return res.status(404).json({
      error: "no such user",
    });
  }
  res.json({
    id: 1,
    email: "ada@example.com",
    name: "Ada",
  });
});
```

```cpp
[[= http::get("/users/{id}")]]
auto user_by_id(int id) -> Result<User> {
  if (id != 1) {
    return std::unexpected(ApiError::not_found("no such user"));
  }
  return User{1, "ada@example.com", "Ada"};
}
```

:::

A missing user is 404 in both. Express picks the JSON. crocket writes a problem-details body (`application/problem+json`). `GET /users/9` comes back with `code` `not_found` and detail `no such user`. The status matches. The body doesn't.

Express still runs the handler for `GET /users/nope`. `Number("nope")` is `NaN`, and `!== 1` sends the same 404 JSON.

## Query parameters

:::pair Express | crocket

```js
app.get("/search", (req, res) => {
  const page = Number(req.query.page ?? 1);
  const q = req.query.q ?? null;
  res.json({ page, q });
});
```

```cpp
struct Search {
  int page = 1;
  std::optional<std::string> q;
};

[[= http::get("/search")]]
auto search(Query<Search> query) -> Search {
  return *query;
}
```

:::

`/search?page=2&q=ada` returns `{"page":2,"q":"ada"}`. A missing query string returns `{"page":1,"q":null}`. `?page=nope` is 422 `query.invalid`, detail `query parameter 'page' is not valid`, and `search` doesn't return that struct. There's no `req.query` object to poke at.

Query values are strings. `??` only replaces `null` or `undefined`, so a missing `page` becomes `1`, and `page=nope` becomes `NaN`. `res.json` writes that as `null` with status 200. Express does not answer 422 for it.

## JSON body and validation

Express won't check the body. You do, or you add a library. crocket decodes JSON straight into the struct. `json::email` and `json::max_len` run as it decodes. A failure is 422 `json.validation`, with one problem body that lists every field.

:::pair Express | crocket

```js
app.post("/users", (req, res) => {
  const email = req.body?.email;
  const name = req.body?.name ?? null;
  if (typeof email !== "string"
      || email.length > 254
      || !email.includes("@")) {
    return res.status(422).json({
      error: "email is not valid",
    });
  }
  res.status(201)
    .location("/users/1")
    .json({ id: 1, email, name });
});
```

```cpp
struct User {
  [[= json::from_path]] std::optional<int> id;
  [[= json::email, = json::max_len(254)]]
  std::string email;
  std::optional<std::string> name;
};

[[= http::post("/users")]]
auto create(Json<User> body) -> Created<User> {
  User user = *body;
  user.id = 1;
  return {user, "/users/1"};
}
```

:::

`id` is `json::from_path`. This route has no `{id}` in the path, so a body that includes `id` is 422 `json.read_only`, and the handler is what fills it in. Unknown JSON fields are ignored. Duplicate keys are an error. An empty `name` is written back as `null`. There's no schema library to keep in sync, because the struct is the schema.

crocket doesn't parse `multipart/form-data` or an HTML form body. `Query<T>` is the query string. A file upload isn't a feature you can reach for yet.

## Status codes

`Created<User>` is 201 plus a `Location` header. `Status<User>` is for the cases that don't have their own wrapper. Returning a struct with no wrapper is 200 and JSON.

:::pair Express | crocket

```js
app.post("/users/:id/archive", (req, res) => {
  const id = Number(req.params.id);
  res.json({
    id,
    email: "ada@example.com",
    name: "Ada",
  });
});
```

```cpp
[[= http::post("/users/{id}/archive")]]
auto archive(int id) -> Status<User> {
  return Status<User>{200, User{id, "ada@example.com", "Ada"}};
}
```

:::

`res.status(204).end()` is `NoContent` in crocket. You don't get a free-form status by returning a number from the handler. If none of the wrappers fit, build a `Response` yourself. The [responses](/guide/v0.5/responses/) chapter is the list.

## Middleware

`app.use` is a chain, and each layer calls `next()`. A crocket fairing is a type with a hook. There's no `next`. `on_request` runs before routing, so it doesn't know which handler matched, and it doesn't read the body. `on_response` runs after the response exists, including errors the framework produced.

:::pair Express | crocket

```js
app.use((req, res, next) => {
  res.set("x-app", "users");
  next();
});
```

```cpp
struct AppHeader {
  auto on_response(const Request&, Response& rs) -> void {
    rs.headers.set("x-app", "users");
  }
};
```

:::

Attach it with `.attach(AppHeader{})`. It runs for every request, not for one router. Route-specific logic belongs in the handler. The [fairings](/guide/v0.5/fairings/) chapter covers `on_ignite` and `on_shutdown` too.

CORS is the same idea. `.attach(Cors::allow_origins({"https://app.example.com"}))` answers the preflight or rejects the origin. There's no `cors` package to configure.

## Errors

Express error middleware is `(err, req, res, next)`, and it has to take all four arguments. A rejected promise from an async handler is passed to that middleware. crocket doesn't have that chain. Return `std::unexpected(ApiError::...)` from a `Result<T>`, or let the extractor fail. A throw the handler didn't catch is 500 `internal`, and `what()` stays out of the body unless you're on the dev profile.

The 404 in `user_by_id` is the pattern. `ApiError::not_found`, `bad_request`, and `unprocessable` are the helpers. Codes are stable strings like `not_found` and `json.validation`, not whatever message you happened to send.

## Auth

Passport sessions, cookie logins, and `express-session` don't have a crocket twin. What you get is a bearer JWT. Link `crocket::auth`, manage one verifier, and mark the route. A missing or bad token is 401. A good token without the role is 403 `auth.forbidden`. Roles come from the token's `roles` claim.

:::pair Express | crocket

```js
import { auth } from "express-oauth2-jwt-bearer";

const checkJwt = auth({
  issuerBaseURL: "https://login.example.com/",
  audience: "users",
});

app.get("/admin", checkJwt, (req, res) => {
  const roles = req.auth.payload.roles ?? [];
  if (!roles.includes("admin")) {
    return res.sendStatus(403);
  }
  res.type("text")
    .send(`hello ${req.auth.payload.sub}\n`);
});
```

|

```cpp
[[= http::get("/admin"), = auth::require("admin")]]
auto admin(Auth<> who) -> std::string {
  return std::format("hello {}\n", who.subject);
}
```

```cpp
  .manage(auth::Jwt::oidc(
      "https://login.example.com/",
      "users"))
```

:::

`auth` is the `express-oauth2-jwt-bearer` package. You configure it once, and the route uses that middleware. A missing or bad token is 401 before the handler runs. The handler checks `roles` and sends 403. `req.auth.payload` is the claims, and `issuerBaseURL` discovers the keys.

`auth::Jwt::oidc` discovers the keys the same way when `jwks` is empty. A token without `admin` in `roles` is 403 `auth.forbidden`. A revoked token stays valid until `exp`. There's no introspection endpoint. `#include <crocket/auth.hpp>` isn't pulled in by `crocket.hpp`.

## Config

Express reads `process.env` wherever you like. crocket keeps one `Config`. Set the fields in code. This program only changes the port:

```cpp
Config cfg;
cfg.server.port = 8080;
```

The [configuration](/guide/v0.5/configuration/) chapter is the rest: limits, timeouts, trusted proxies, TLS. I'm not pasting environment variable names here. If you need them, they're on that page, and anything you set in code after reading the environment wins.

## Static files

`express.static` serves a directory. crocket does too, or it serves bytes you embedded with `#embed`. Routes are matched first, so a file named `healthz` can't hide `GET /healthz`.

:::pair Express | crocket

```js
app.use("/assets",
  express.static("public"));
```

```cpp
  .mount("/assets",
      files{.root = "public"});
```

:::

The [responses](/guide/v0.5/responses/) chapter has the cache and header rules.

## Logs and metrics

You'd add `pino-http` or `morgan`, and `prom-client` if you want Prometheus. Both are built in. Attach them.

```cpp
  .attach(Logger{})
  .attach(Metrics{})
```

`Logger` writes one structured line per request. The route template is in the line, not the raw path, so `/users/1` doesn't blow up the cardinality. `Authorization` and `Cookie` are dropped. `Metrics` serves Prometheus text at `GET /metrics`. It isn't StatsD and it isn't OpenTelemetry. One scraper per process. Two scrapers would each see half of a counter.

## OpenAPI

Express won't write the spec from the route table. You maintain a document, or a library reads comments. crocket writes OpenAPI 3.1 from the handlers at startup.

```cpp
  .attach(OpenApi{{
      .title = "Users",
      .version = "1.0.0"}})
```

`GET /openapi.json` is that document. `.docs = "/docs"` also serves a Swagger UI page, and that page loads its script from `cdn.jsdelivr.net`. If your content security policy only allows your own origin, leave `.docs` unset and serve the JSON yourself. This site does it that way.

## Tests

Supertest drives the Express app without a port. `LocalClient` drives crocket's real pipeline, fairings included, without a socket.

:::pair Express | crocket

```js
import request from "supertest";
import { app } from "./server.js";

const created = await request(app)
  .post("/users")
  .send({
    email: "ada@example.com",
    name: "Ada",
  });
assert.equal(created.status, 201);

const missing = await request(app)
  .get("/users/9");
assert.equal(missing.status, 404);
```

```cpp
LocalClient client(app);

auto created = client.post("/users")
    .json("{\"email\":"
          "\"ada@example.com\","
          "\"name\":\"Ada\"}")
    .dispatch();
assert(created.status == 201);

auto missing = client.get("/users/9").dispatch();
assert(missing.status == 404);
```

:::

Constructing `LocalClient` ignites the app and throws if ignite fails. Handlers are still plain functions, so you can call `user_by_id(1)` with no client at all. The [testing](/guide/v0.5/testing/) chapter has the rest.

## Docker

The image has to provide GCC 16.2's `libstdc++`, because that's what the binary was built with. The toolchain image does. The port is 8080 because `users.cpp` sets it.

:::pair Express | crocket

```dockerfile
FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY server.js .
EXPOSE 8080
CMD ["node", "server.js"]
```

```dockerfile
FROM ghcr.io/sean3z/crocket-toolchain:gcc-16.2
COPY . /src
WORKDIR /src
ENV CC=/opt/gcc-16.2/bin/gcc-16.2 \
    CXX=/opt/gcc-16.2/bin/g++-16.2
RUN cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=$CC \
      -DCMAKE_CXX_COMPILER=$CXX \
 && cmake --build build \
 && install -m755 build/users \
      /usr/local/bin/users
EXPOSE 8080
CMD ["users"]
```

:::

The [deploying](/guide/v0.5/deploying/) chapter covers TLS, the drain on SIGTERM, and `/healthz` versus `/readyz`. Use `/healthz` for liveness and `/readyz` for readiness.

## What's different

You compile. There's no reload-on-save. A wrong capture name is a compiler error, not a 404 you find in staging.

Annotations are the route table. You don't call `app.get` and hope you remembered every path. `reflect_routes<^^api>()` reads the functions while compiling.

Fairings aren't middleware. They don't call `next`, they don't see the parsed body, and `on_request` runs before the route is chosen.

There's no session store, no template engine, and no multipart parser. WebSockets, server-sent events, and streamed bodies aren't built. What's planned is [issue 37](https://github.com/sean3z/crocket/issues/37).

The memory and the throughput are measured, not guessed. [todo.crocket.dev](https://todo.crocket.dev) is a real app on this stack, not a sample pasted into a README.

## What you'd still install

crocket shows up with the boring production pieces already in the binary. Express is a fine router. The rest of this is the mall you walk through before the app feels finished.

:::parity express

`express.static` already handles files and ETags, so that row isn't a package. crocket doesn't rate-limit requests or gzip a response body, so those packages aren't in the pile either. The byte counts are published package sizes, not an installed `node_modules` and not a container image.

## By the numbers

Express isn't in this shootout. The Node column is Fastify, one process, which is the name on the homepage.

:::numbers node

:::cta
primary /guide/v0.5/quickstart/ Quickstart
/guide/v0.5/migrate-spring/ From Spring Boot
https://todo.crocket.dev Todo demo
:::
