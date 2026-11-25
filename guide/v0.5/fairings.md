# Fairings

Fairings are structured middleware. A fairing is any movable type with one or more of the hooks below. There is no base class and no `info()` function.

## Hooks

| Hook | When | Can |
|---|---|---|
| `on_ignite(Ignite&)` | During ignite, in attach order | Inspect state, config, and routes. `ig.fail` aborts launch. |
| `on_request(Request&)` | Before routing, in attach order | Rewrite the request, or return a `Response` and stop the chain. |
| `on_response(const Request&, Response&)` | After the response exists, in reverse attach order | Rewrite the response. |
| `on_shutdown()` | After the drain, in reverse attach order | Flush and close. |

`on_request` can answer the request. Returning a `Response` stops the chain, which is how maintenance mode and CORS preflights work. `on_response` runs on every response, including the engine's 413, 503, and 504, so logs and metrics don't miss a request. The first fairing you attach sees the request first and the response last.

Fairings run concurrently on worker threads. Keep shared state thread-safe. They are short and synchronous. They don't parse request bodies.

A response timer:

```cpp
struct Timer {
  auto on_response(const Request& rq, Response& rs) -> void {
    auto us = std::chrono::duration_cast<std::chrono::microseconds>(
                  Clock::now() - rq.received)
                  .count();
    rs.headers.set("x-response-time", std::format("{} us", us));
  }
};
```

## Shield

Shield is attached by default, last, so its `on_response` runs first. It sets:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`
- `Referrer-Policy: no-referrer`
- `Strict-Transport-Security: max-age=31536000` on HTTPS, never for localhost

A header the response already carries is left alone. That is how a handler, or a static-file `.headers` rule, replaces the content security policy for HTML and leaves every other response on the default. `Shield::none()` sends nothing. Attach your own to change one field:

```cpp
app.attach(Shield{}.set("content-security-policy", "default-src 'self'")
               .remove("x-frame-options"));
```

The default policy blocks a browser page from loading its own scripts and styles. A page you serve has to set a policy it can live under. This site's HTML uses `default-src 'self'` with no inline script or style.

## CORS, logs, and metrics

`Cors` is deny-by-default. `Cors::allow_origins({...})` takes methods, headers, exposed headers, credentials, and a max age. It answers preflights itself, or 403 `cors.denied` for an origin that is not on the list. It refuses at ignite to combine credentials with `*`. Without `Cors`, no cross-origin headers are sent.

`Logger` writes one line per request: request and trace ids, method, route template (never the raw path), handler, status, error code, duration, bytes, protocol, client, user agent, and the authenticated subject. `Authorization`, `Proxy-Authorization`, and `Cookie` are removed from log lines. Field names that look like credentials are redacted, and `-` and `_` count as the same character, so `X-Api-Key` matches `api_key`.

`Metrics` serves Prometheus text at `GET /metrics`, labeled by route template. The series include `crocket_http_requests_total`, a duration histogram, in-flight requests, extractor failures, connections, worker gauges, and `crocket_build_info{version,commit,compiler,hostname}`. `crocket_saturation` (0 to 1) combines the capacity signals for an HPA or KEDA target; see [Scaling](/guide/v0.5/scaling/). Scrape each pod from one Prometheus. Two scrapers would each see half of a counter that is not shared.

`CROCKET_METRICS_LABELS` adds labels. A Kubernetes Service named `crocket` injects `CROCKET_PORT=tcp://...`, which crocket refuses to start with. Set `enableServiceLinks: false`, or name the Service something else.

## Health checks

Every app gets two built-in routes.

- `GET /healthz` answers 200 `{"status":"ok"}` while the process is serving. Use it for liveness.
- `GET /readyz` answers 200 `{"status":"ready","checks":{...}}` when every readiness check passes, and 503 `not_ready` when one fails. The checks are each managed type with `bool ready() const`, and the database pool's `select 1`. During the drain on shutdown it answers 503 `server.draining`.

Static files mounted at `/` do not swallow these. Routes match first.
