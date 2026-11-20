# State

`manage` a value once. Ask for it with `State<T>` on any route. The same mechanism holds a database pool and an outbound HTTP client.

## Managed state

A route that needs state nobody manages fails at ignite, before the server accepts a connection:

```text
ignite failed:
  - GET /items/{id} (api::item) requires State<Store>, but Store is not managed
```

Ignite also rejects conflicting routes and anything a fairing's `on_ignite` flags. Every problem is reported at once.

Managed state is destroyed in reverse `manage` order at shutdown, after requests have drained. A type with `bool ready() const` is part of `/readyz`. While it returns false, `/readyz` is 503 `not_ready`.

`State<T>` is never a request-time failure. If the program is serving, the value is there.

## Databases

`crocket::db` is the API (`Db&`, `find`, `insert`, `where`, and the rest). Each database is a backend you link. Today there is one, `crocket::pg`, Postgres on libpqxx. Another backend is not in this tree. Core crocket never includes it. You link `crocket::pg` when you want it, which needs libpqxx built with the same GCC and C++26. `CROCKET_PG=OFF` skips it. `ON` makes a missing libpqxx an error. libpqxx 7.10 and 8.x both work.

Handlers name `Db&`, never the backend. Your structs stay plain: no annotations and no base class.

```cpp
struct Hero {
  std::int64_t id;
  std::string name;
  std::string alias;
  std::optional<std::string> mentor;
};

[[= http::get("/heroes/{id}")]]
auto get(Db& db, std::int64_t id) -> std::optional<Hero> {
  return db.find<Hero>(id);  // nullopt: 404
}
```

Reflection reads the struct while compiling.

- The table is the type's name in plural snake_case. `Hero` is `heroes`. Specialize `crocket::db::table_name<Hero>` to use another name.
- The columns are the data members, by name and in declaration order. The member named `id` is the key. The database fills it in on insert.
- `std::optional<T>` reads and writes `NULL`.
- An `id` may be left out of a JSON body. `insert` never sends it. An id a client does send is ignored on insert.

`db.find`, `insert`, `update`, and `erase` build their SQL at compile time. Filters name columns with member pointers (`db.where(&Hero::mentor, "Bruce Wayne")`), so a typo does not compile. `db.sql` and `db.exec` are the escape hatches. A unique violation on insert is 409 `db.conflict`.

`db::Pool` opens `pool_size` connections (default 8) when it is constructed and throws if it cannot, so a database that is down at startup stops the process. After that, `GET /readyz` runs `select 1` and returns 503 while the check fails or while the server is draining. A handler that cannot check out a connection gets 503 `db.busy`.

A query blocks the worker running its handler. Unless you set the worker count yourself, crocket raises it to the pool size. With `CROCKET_DATABASE_POOL_SIZE=16` on a 4-core machine you get 16 workers, not 4. Idle workers sleep. Each extra thread costs about 8 MB of virtual stack, not resident memory, and no CPU while idle. The worker count is capped at 1,024. A count you set yourself is used as is, even when it is smaller than the pool.

Routes that never take `Db&` pay nothing for this. With metrics attached you get `crocket_db_seconds`, pool gauges, and `db_ms` on the log line.

`CROCKET_DATABASE_URL` is the connection string. Empty leaves libpq's `PG*` variables.

## Outbound HTTP

`crocket::client` is optional outbound HTTP on h2o's client, on one of the server's event loops. There is no second network stack and no blocking call. Every method returns `Task`. Link `crocket::client` and include `<crocket/client.hpp>`. A program that does not link it does not get the client. `CROCKET_CLIENT` is `AUTO` (build it when OpenSSL 3 is present), `ON`, or `OFF`.

```cpp
return build(Config::from_env())
    .manage(http::Client{{
        .base = base,
        .timeout = 2s,
        .pool = 64,
        .retry = retry::idempotent(3),
        .breaker = breaker::consecutive(5, 30s),
    }})
    .mount("/", reflect_routes<^^api>())
    .launch();
```

A route takes `State<http::Client>` and `co_await`s `get` or `post`. Retries and the breaker are on unless a call opts out (`{.retry = retry::none}`). Only idempotent methods are retried, plus any call that sets `Idempotency-Key`. A retry budget caps retries at 20% of recent calls, at least 3. Failures are `upstream.timeout` (504), `upstream.unavailable` (503), and `upstream.circuit_open` (503).

Two services are two clients: `.with_state<Tag>()` and `State<http::Client::For<Tag>>`. An inbound `x-request-id` is forwarded. `traceparent` is not.

`examples/client.cpp` is `crocket_client_example`. It reads `UPSTREAM_BASE` and defaults to `http://127.0.0.1:9`, which refuses connections so the routes answer 503 until you point it somewhere.
