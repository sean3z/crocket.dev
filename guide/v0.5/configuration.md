# Configuration

One `Config` holds the server, the limits, the timeouts, the proxy, and the profile. Optional pieces read their own groups: `auth` for `crocket::auth`, `database` for `crocket::db`. Core crocket never opens a database or fetches a JWKS on its own.

## Precedence

Settings stack, and each layer beats the one before it:

1. The built-in defaults, or the `Config` you pass to `from_env` when your program wants different ones.
2. The dev profile, when `CROCKET_PROFILE=dev`.
3. The other `CROCKET_*` environment variables.
4. Whatever you assign in code after `from_env` returns.
5. The fields you pass to `launch({...})`.

```cpp
Config cfg = Config::from_env({.server = {.port = 50051}});
cfg.timeouts.request = 10s;
return crocket::build(cfg)
    .mount("/", reflect_routes<^^api>())
    .launch({.listen = "0.0.0.0:50051"});
```

`from_env`'s argument replaces the built-in defaults, and the environment can still override it. That is how a gRPC server defaults to port 50051 without ignoring `CROCKET_PORT`. `launch()` with no argument serves on `cfg.server`. `.listen` takes `"8080"`, `":8080"`, `"0.0.0.0:8080"`, or `"[::1]:8080"`.

A value that does not parse throws `std::invalid_argument` naming the variable, so a typo stops the program at startup. Sizes take `K`, `M`, or `G` (powers of 1024). Durations take `ms`, `s`, `m`, or `h`, and a bare number is seconds. Booleans are `true`/`false`, `1`/`0`, `yes`/`no`, or `on`/`off`. Lists are comma-separated. Unset or empty leaves the setting alone.

## Limits

Every resource a client can make the server hold has a bound. Past it, the request fails or the connection waits, as the table says. The defaults follow h2o for connections and HTTP/2, and Rocket for a JSON body.

| Limit | Default | Past it |
|---|---|---|
| `max_connections` | 1024 | New connections wait in the accept queue |
| `max_connections_per_ip` | 0 (none) | A new connection from that address is closed |
| `http2_max_streams` | 100 | Advertised in the HTTP/2 SETTINGS |
| `max_header_bytes`, `max_header_count` | 8 KiB, 100 | 431 `headers.too_large` |
| `max_body_bytes` | 1 MiB | 413 `body.too_large` |
| `max_body_memory` | 256 MiB | 503 `server.busy` |
| `etag_max_bytes` | 1 MiB | No automatic ETag |
| `max_in_flight` | 1024 | 503 `server.busy` |
| `timeouts.request` | 30 s | 504 `deadline.exceeded` |
| `timeouts.drain` | 10 s | In-flight requests are dropped after this |

`max_connections_per_ip` is off by default because, behind a load balancer, every connection comes from the balancer. Set it when clients connect directly. h2o also closes a connection that takes more than 10 seconds to send its headers, or that sits idle on HTTP/2 for 10 seconds (GOAWAY).

## Dev profile

`CROCKET_PROFILE=dev` selects `Config::dev()`. Unset or `release` uses the release defaults. The dev profile binds `127.0.0.1` when the host is empty, prints every route, turns on `GET /__routes`, puts error detail in the body, uses a one-hour deadline, and drains in one second. Its logs are readable lines. Release logs are structured. `allowed_hosts` in the dev profile also accepts `localhost`, `127.0.0.1`, and `::1`.

## Behind a proxy

`Client` reports the peer address and whether the connection was `https` or `http`. Behind a proxy, list the proxies you run. crocket then takes both from the header they add.

```cpp
Config cfg;
cfg.proxy.trusted = {"10.0.0.0/8"};
cfg.proxy.header = ProxyHeader::XForwardedFor;  // the default
cfg.proxy.allowed_hosts = {"api.example.com", "*.example.com"};
```

Only trusted proxies are believed. Behind a chain, the client is the first address that no trusted proxy is behind, so a value the client wrote into `X-Forwarded-For` itself is never picked. Only the configured header is read. The other is ignored.

`allowed_hosts` is the host names the server answers. Any other `Host` (`:authority` on HTTP/2) is 400 `host.invalid` before routing. Ports are not compared. `*.example.com` matches subdomains and not `example.com` itself. An empty list allows every host. A malformed entry fails ignite.

`CROCKET_TRUSTED_PROXIES`, `CROCKET_PROXY_HEADER` (`x-forwarded-for` or `forwarded`), and `CROCKET_ALLOWED_HOSTS` set the same fields.

## Environment variables

The names you set most often:

| Variable | Default |
|---|---|
| `CROCKET_PROFILE` | `release` |
| `CROCKET_PORT` | `8000` |
| `CROCKET_HOST` | `0.0.0.0` (`127.0.0.1` in dev) |
| `CROCKET_LISTEN` | unset. Replaces host and port |
| `CROCKET_TLS_CERT`, `CROCKET_TLS_KEY` | unset. TLS needs both |
| `CROCKET_HTTP2` | `true` |
| `CROCKET_H2_PRIOR_KNOWLEDGE` | `false` |
| `CROCKET_WORKERS` | at least 4, one per core, raised to the largest blocking pool |
| `CROCKET_EVENT_LOOPS` | one per physical core |
| `CROCKET_LOG_LEVEL` | `info` (`debug` in dev) |
| `CROCKET_LOG_SAMPLE` | `1` (every successful request) |
| `CROCKET_LOG_SLOW` | `500ms` |
| `CROCKET_REQUEST_TIMEOUT` | `30s` (an hour in dev) |
| `CROCKET_DRAIN_TIMEOUT` | `10s` (`1s` in dev) |
| `CROCKET_DATABASE_URL` | unset (libpq's `PG*` variables) |
| `CROCKET_DATABASE_POOL_SIZE` | `8` |
| `CROCKET_AUTH_ISSUER`, `CROCKET_AUTH_AUDIENCE`, `CROCKET_AUTH_JWKS` | unset |
| `CROCKET_AUTH_SECRET` | unset (HMAC off) |

`CROCKET_AUTH_*` and `CROCKET_DATABASE_*` do nothing until you link `crocket::auth` or `crocket::pg` and construct the verifier or the pool from `cfg`. The limit variables (`CROCKET_MAX_BODY_BYTES` and the rest) map onto the table above, one name per field.
