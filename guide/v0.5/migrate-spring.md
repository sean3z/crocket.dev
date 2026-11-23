# Migrating from Spring Boot

A `@RestController` method and a crocket handler are doing the same job. The method is the route. The arguments are the path, the query, and the body. What you return is the response. crocket just refuses to discover any of that by scanning the classpath at startup. It reads the functions while it compiles.

The crocket column is `checks/snippets/users.cpp`, compiled against commit `9b446f8`. The [Express](/guide/v0.5/migrate-express/) page uses the same program. `POST /users` with `{"email":"ada@example.com","name":"Ada"}` answers 201, `Location: /users/1`, and `{"id":1,"email":"ada@example.com","name":"Ada"}` on both sides.

## Project and build

Spring Boot is a starter and a plugin. crocket is a library fetched at configure time. You need GCC 16.2. `crocket::auth` is here only for the JWT route.

:::pair Spring Boot | crocket

```java
plugins {
  id("org.springframework.boot") version "3.5.0"
  id("io.spring.dependency-management") version "1.1.7"
}
dependencies {
  implementation("org.springframework.boot:spring-boot-starter-web")
  implementation("org.springframework.boot:spring-boot-starter-validation")
  implementation("org.springframework.boot:spring-boot-starter-oauth2-resource-server")
}
```

```cmake
cmake_minimum_required(VERSION 3.28)
project(users CXX)

include(FetchContent)
FetchContent_Declare(crocket
  GIT_REPOSITORY https://github.com/sean3z/crocket.git
  GIT_TAG 9b446f8c2423262ef1cbf3afe370a0ae2f81d181)
FetchContent_MakeAvailable(crocket)

add_executable(users users.cpp)
target_link_libraries(users PRIVATE crocket::crocket crocket::auth)
```

:::

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++-16.2
cmake --build build
./build/users
```

There's no annotation processor and no `target/classes`. The binary is the server. Tag `0.5.1` doesn't include static files. Pin `9b446f8` when you need them. The [quickstart](/guide/v0.5/quickstart/) is the short form.

## Listen

`server.port` is a property. crocket's port is a field. This program uses 8080, same as a Spring app that sets `server.port=8080`.

:::pair Spring Boot | crocket

```java
@SpringBootApplication
public class UsersApplication {
  public static void main(String[] args) {
    SpringApplication.run(UsersApplication.class, args);
  }
}
```

```cpp
Config cfg;
cfg.server.port = 8080;
```

:::

`main` builds the app from that config and returns `app.launch()`. Tomcat isn't a separate choice. h2o is the wire engine, and your handlers never include its headers. `GET /healthz` is already there.

## Path parameters

`@PathVariable` and `{id}` are the same idea. The difference is when the check happens. crocket won't call the function if `id` isn't an `int`.

:::pair Spring Boot | crocket

```java
@GetMapping("/users/{id}")
ResponseEntity<User> userById(@PathVariable int id) {
  if (id != 1) return ResponseEntity.notFound().build();
  return ResponseEntity.ok(new User(1, "ada@example.com", "Ada"));
}
```

```cpp
[[= http::get("/users/{id}")]]
auto user_by_id(int id) -> Result<User> {
  if (id != 1) return std::unexpected(ApiError::not_found("no such user"));
  return User{1, "ada@example.com", "Ada"};
}
```

:::

Spring's 404 from `notFound().build()` has an empty body. crocket's 404 is problem details, `application/problem+json`, with `code` `not_found`. Same status, different body. `GET /users/nope` is also 404 in crocket, and it's `path.invalid`, because the capture didn't parse.

## Query parameters

:::pair Spring Boot | crocket

```java
public record Search(int page, String q) {}

@GetMapping("/search")
Search search(@RequestParam(defaultValue = "1") int page,
              @RequestParam(required = false) String q) {
  return new Search(page, q);
}
```

```cpp
struct Search {
  int page = 1;
  std::optional<std::string> q;
};

[[= http::get("/search")]]
auto search(Query<Search> query) -> Search { return *query; }
```

:::

One struct is the whole query string. You don't repeat the names as `@RequestParam`s. A missing `page` stays `1`. A value that isn't an integer is 422 `query.invalid`.

## JSON body and validation

`@Valid` on a record is Jakarta Bean Validation. crocket's annotations sit on the members and run while the JSON is decoded. You don't register a `MappingJackson2HttpMessageConverter`. The struct is the schema.

:::pair Spring Boot | crocket

```java
public record NewUser(
    @Email @NotBlank @Size(max = 254) String email,
    @Size(max = 80) String name) {}

@PostMapping("/users")
ResponseEntity<User> create(@Valid @RequestBody NewUser body) {
  var user = new User(1, body.email(), body.name());
  return ResponseEntity.created(URI.create("/users/1")).body(user);
}
```

```cpp
struct NewUser {
  [[= json::email, = json::max_len(254)]] std::string email;
  std::optional<std::string> name;
};

[[= http::post("/users")]]
auto create(Json<NewUser> body) -> Created<User> {
  User user{1, body->email, body->name};
  return {user, "/users/1"};
}
```

:::

Spring's default for a `@Valid` failure is 400. crocket's is 422 `json.validation`, and every failing field is in that one body. If you need Spring to answer 422 too, map `MethodArgumentNotValidException` yourself. I'm not going to pretend the defaults match.

`name` is optional in the crocket struct. Leave it out and the response writes `null`. There's no `@Size` on that optional in this example. Length checks apply to the string itself.

crocket doesn't read `multipart/form-data` or an HTML form. A file upload isn't hiding under another annotation.

## Status codes

`ResponseEntity.created` is `Created<T>`. `ResponseEntity.ok` is a plain return, or `Status<T>` when you want the code written down. `ResponseEntity.noContent()` is `NoContent`.

:::pair Spring Boot | crocket

```java
@PostMapping("/users/{id}/archive")
User archive(@PathVariable int id) {
  return new User(id, "ada@example.com", "Ada");
}
```

```cpp
[[= http::post("/users/{id}/archive")]]
auto archive(int id) -> Status<User> {
  return Status<User>{200, User{id, "ada@example.com", "Ada"}};
}
```

:::

Returning a record from a `@RestController` method is 200 and JSON. Returning a crocket struct is the same. `@ResponseStatus` doesn't have a twin. Use `Status<T>`, `Created<T>`, or a `Response` you fill in. The wrappers are listed in [responses](/guide/v0.5/responses/).

## Filters and interceptors

A `OncePerRequestFilter` calls `chain.doFilter`. A `HandlerInterceptor` has `preHandle` and `postHandle` around a controller it already chose. A crocket fairing has neither. `on_request` runs before routing, so the handler isn't chosen yet and the body isn't parsed. `on_response` runs after, for errors too.

:::pair Spring Boot | crocket

```java
@Component
class AppHeader extends OncePerRequestFilter {
  @Override
  protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
      throws ServletException, IOException {
    res.setHeader("x-app", "users");
    chain.doFilter(req, res);
  }
}
```

```cpp
struct AppHeader {
  void on_response(const Request&, Response& rs) { rs.headers.set("x-app", "users"); }
};
```

:::

`.attach(AppHeader{})` is the registration. There's no component scan. A filter that should only wrap `/users/**` doesn't have a matcher here. Put that logic in the handler, or look at `rq.path` yourself and accept that you're early.

CORS is `.attach(Cors::allow_origins({"https://app.example.com"}))`. That's the whole allow-list. It answers the preflight.

## Errors

`@ControllerAdvice` and `@ExceptionHandler` are how Spring turns an exception into a body. crocket handlers return the error instead of throwing it. `std::unexpected(ApiError::not_found("no such user"))` is the 404 above.

An exception you didn't catch is 500 `internal`. The client doesn't get `what()`, except on the dev profile, where the detail is included. There's no `@ResponseStatus(HttpStatus.CONFLICT)` on an exception type. Build the `ApiError` with the status you want: `not_found`, `bad_request`, `unprocessable`.

## Auth

`spring-boot-starter-oauth2-resource-server` plus `hasRole("admin")` is the Spring shape. crocket's is a managed verifier and an annotation. No security filter chain, no `SecurityFilterChain` bean.

:::pair Spring Boot | crocket

```java
@GetMapping("/admin")
public String admin(@AuthenticationPrincipal Jwt jwt) {
  return "hello " + jwt.getSubject() + "\n";
}
```

```cpp
[[= http::get("/admin"), = auth::require("admin")]]
auto admin(Auth<> who) -> std::string { return std::format("hello {}\n", who.subject); }
```

:::

Spring still needs the resource-server config that demands the role. crocket puts that on the function. The verifier is this value:

```cpp
      .manage(auth::Jwt{
          .issuer = "https://login.example.com/",
          .audience = "users",
          .jwks = "https://login.example.com/.well-known/jwks.json",
      })
```

A missing token is 401. A token without `admin` in its `roles` claim is 403 `auth.forbidden`. There's no session and no remember-me. A token you revoke at the issuer keeps working until `exp`, because nothing calls an introspection endpoint. Include `<crocket/auth.hpp>` yourself. `crocket.hpp` doesn't.

## Config

`application.properties` and `@Value` scatter configuration through the app. crocket keeps one `Config` and you set the fields.

```cpp
Config cfg;
cfg.server.port = 8080;
```

That's the whole port setup for this program. Limits, timeouts, proxies, and TLS are the same object. They're documented in [configuration](/guide/v0.5/configuration/), including the environment variables that can override a field. This page doesn't repeat those names. Values you assign after the environment is read are the ones that stick.

`@ConfigurationProperties` doesn't have an equivalent generator. It's a struct you write.

## Static files

Spring serves `classpath:/static/` because the starter says so. crocket serves a directory, or bytes embedded with `#embed`, only where you mount them.

:::pair Spring Boot | crocket

```java
@Configuration
class Assets implements WebMvcConfigurer {
  @Override
  public void addResourceHandlers(ResourceHandlerRegistry registry) {
    registry.addResourceHandler("/assets/**").addResourceLocations("file:public/");
  }
}
```

```cpp
      .mount("/assets", files{.root = "public"});
```

:::

Routes win over files, so `/healthz` still hits the built-in handler. Static files need commit `9b446f8`. They aren't in tag `0.5.1`. Cache rules and a content security policy for HTML are in [responses](/guide/v0.5/responses/).

## Logs and metrics

Actuator plus Micrometer is a starter and a registry. crocket's log and metrics are two fairings.

```cpp
      .attach(Logger{})
      .attach(Metrics{})
```

`Logger` writes one line per request, with the route template rather than the raw path. `Cookie` and `Authorization` don't get logged. `Metrics` is Prometheus text at `GET /metrics`. It isn't Micrometer, and it doesn't speak the other backends. Scrape each process once.

## OpenAPI

springdoc scans the controllers and serves `/v3/api-docs` plus a Swagger UI. crocket builds the document from the same reflection that built the routes. There's no extra dependency.

```cpp
      .attach(OpenApi{{.title = "Users", .version = "1.0.0"}})
```

The JSON is `GET /openapi.json`. Set `.docs = "/docs"` if you also want the Swagger UI page. That page loads its script from `cdn.jsdelivr.net`. A content security policy of `default-src 'self'` won't allow it, so leave `.docs` unset and ship the JSON. That's what this site does.

## Tests

`@WebMvcTest` and `MockMvc` boot a slice of Spring. `LocalClient` boots the crocket pipeline in-process. No socket, same fairings the server uses.

:::pair Spring Boot | crocket

```java
@WebMvcTest(UsersController.class)
class UsersTest {
  @Autowired MockMvc mvc;

  @Test
  void createsAndMisses() throws Exception {
    mvc.perform(post("/users").contentType(APPLICATION_JSON)
            .content("{\"email\":\"ada@example.com\",\"name\":\"Ada\"}"))
        .andExpect(status().isCreated());
    mvc.perform(get("/users/9")).andExpect(status().isNotFound());
  }
}
```

```cpp
    LocalClient client(app);
    auto created = client.post("/users").json(R"({"email":"ada@example.com","name":"Ada"})").dispatch();
    assert(created.status == 201);
    auto missing = client.get("/users/9").dispatch();
    assert(missing.status == 404);
```

:::

You can also call `user_by_id(1)` directly. It's a function. `LocalClient` is what you want when the test cares about status codes, headers, and fairings. More of the client is in [testing](/guide/v0.5/testing/).

## Docker

A JRE image runs a jar. The crocket image has to be the GCC 16.2 toolchain, or another image that can load that `libstdc++`. The process listens on 8080 because the code says so.

:::pair Spring Boot | crocket

```dockerfile
FROM eclipse-temurin:21-jre
COPY build/libs/users.jar /app/users.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/users.jar"]
```

```dockerfile
FROM ghcr.io/sean3z/crocket-toolchain:gcc-16.2
COPY . /src
WORKDIR /src
RUN cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=/opt/gcc-16.2/bin/gcc-16.2 \
      -DCMAKE_CXX_COMPILER=/opt/gcc-16.2/bin/g++-16.2 \
 && cmake --build build \
 && install -m755 build/users /usr/local/bin/users
EXPOSE 8080
CMD ["users"]
```

:::

`/healthz` is liveness. `/readyz` is readiness, and it goes 503 as soon as the process starts draining. The [deploying](/guide/v0.5/deploying/) chapter has TLS and the signal handling.

## What's different

There's a compile step. Spring rebuilds a jar and restarts the JVM. crocket rebuilds a binary. A capture whose name doesn't match the parameter fails the build, and the error names both.

You don't scan for controllers. `reflect_routes<^^api>()` is the scan, and it happens in the compiler. The annotations on the function are the request mapping.

Filters aren't fairings. Nothing calls `doFilter`, `on_request` is before the route is chosen, and a fairing doesn't get the decoded body.

There's no Spring Data, no session, and no Thymeleaf. An optional Postgres library exists (`crocket::pg`). It isn't JPA, and this page doesn't invent a repository API for it. Multipart uploads aren't implemented. WebSockets, server-sent events, and streamed bodies aren't either. The list of what's planned is [issue 37](https://github.com/sean3z/crocket/issues/37).

On the Heroes CRUD rig, crocket's peak was 21 MB and 35.2k req/s. Spring Boot's peak on that same run was 471 MB and 8.4k req/s, with the JVM left untuned. Read the hardware and the caveats in [By the numbers](/#numbers) and in [Where the cycles go](https://rambling.hashnode.dev/where-the-cycles-go-c-26-rust-java-and-node-on-one-crud-api-d400dd228d21) before you quote either number. [todo.crocket.dev](https://todo.crocket.dev) is a running app, if you want to see the framework do more than answer `/users/1`.
