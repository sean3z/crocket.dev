# Deploying

The release profile listens on `0.0.0.0:8000`. Put a proxy in front of it for TLS if you don't want crocket to terminate TLS itself. `launch({.tls_cert = ..., .tls_key = ...})` or `CROCKET_TLS_CERT` and `CROCKET_TLS_KEY` turn on HTTPS, and HTTP/2 is negotiated with ALPN when `server.http2` is true (the default).

With TLS on, it reloads the certificate and key on SIGHUP and when either file changes and then stays the same for a second. A certificate that does not load, or does not match its key, is logged and the previous one stays in use.

## Docker

Published images:

- `ghcr.io/sean3z/crocket-hello`, tagged `:@release@`, `:0.5`, and `:stable` for the stable release, and `:latest` for `main`. Pin `:@release@` in anything you deploy. The tags are signed with Sigstore.
- `ghcr.io/sean3z/crocket-toolchain:gcc-16.2`, Ubuntu 26.04 with GCC 16.2. `:gcc-16.2-pg` adds libpqxx built with that GCC.

A Dockerfile for the [quickstart](/guide/v0.5/quickstart/) app, in the toolchain image so GCC 16.2's `libstdc++` is there at run time:

```dockerfile
FROM ghcr.io/sean3z/crocket-toolchain:gcc-16.2
COPY . /src
WORKDIR /src
RUN cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER=/opt/gcc-16.2/bin/gcc-16.2 \
      -DCMAKE_CXX_COMPILER=/opt/gcc-16.2/bin/g++-16.2 \
      -DCMAKE_EXE_LINKER_FLAGS="-Wl,-rpath,$(dirname $(/opt/gcc-16.2/bin/g++-16.2 -print-file-name=libstdc++.so))" \
 && cmake --build build \
 && install -m755 build/hello_app /usr/local/bin/ \
 && rm -rf /src/build
EXPOSE 8000
CMD ["hello_app"]
```

Linking with `-Wl,--gc-sections` drops the parts of h2o a program never calls, about 300 KB. h2o is linked statically. OpenSSL stays dynamic, under the Apache License 2.0. A binary you distribute has to include h2o's notices and the notices of the libraries it bundles (picotls, quicly, picohttpparser, hiredis, libyrmcds, libgkc, and cloexec).

## Kubernetes

Use `/healthz` for liveness and `/readyz` for readiness. `/readyz` turns 503 as soon as the drain starts, and while a managed pool or the database is down. Set `CROCKET_EVENT_LOOPS` to the CPU limit. crocket counts the CPUs in its affinity mask, which a CPU quota doesn't change.

A Service named `crocket` makes Kubernetes inject `CROCKET_PORT=tcp://...`, which crocket refuses to start with. Set `enableServiceLinks: false`, or name the Service something else.

The hello image does not attach `Metrics`. Your app does, if you want `/metrics`. Scrape each pod directly. Two scrapers would each see half of the counters. How to read `crocket_saturation`, and when more pods won't help, is in [Scaling](/guide/v0.5/scaling/).

## Graceful shutdown

On SIGINT or SIGTERM, `/readyz` turns 503 `server.draining`, and crocket stops accepting. In-flight requests are answered with `Connection: close` and drained for up to `timeouts.drain` (`CROCKET_DRAIN_TIMEOUT`, 10 seconds by default, 1 second in the dev profile). Then `on_shutdown` runs, in reverse attach order, and managed state is destroyed in reverse `manage` order.

A `preStop` sleep keeps the pod serving until the Service has stopped sending it new connections. Keep `terminationGracePeriodSeconds` above that sleep, plus the drain, plus your slowest request. With a 5 second `preStop` and a 10 second drain, `terminationGracePeriodSeconds: 30` leaves 15 seconds for the slowest request:

```yaml
spec:
  terminationGracePeriodSeconds: 30  # > preStop + drain + slowest request
  containers:
    - name: hello
      env:
        - name: CROCKET_DRAIN_TIMEOUT
          value: 10s
      readinessProbe:
        httpGet: {path: /readyz, port: http}
      lifecycle:
        preStop:
          exec: {command: ["sleep", "5"]}
```

During a rollout, `crocket_http_requests_in_flight` is how many requests the leaving pod is still handling. `crocket_requests_abandoned_total` counts requests dropped while waiting for a worker, and 504s in `crocket_http_requests_total` are deadlines that expired.

## The wire engine

The framework layer knows nothing about sockets. `Crocket::handle` is the whole contract, and `LocalClient` drives that function. `src/engine_h2o.cpp` is the only translation unit that includes `<h2o.h>`. h2o is linked `PRIVATE`, built as `libh2o-evloop` with mruby, brotli, zstd, io_uring, and the shared library off.

Network I/O runs on one event loop per physical core in the process's affinity mask. On a 16-core, 32-thread machine, 16 loops served about 1.6 times the requests of 32, because two loops sharing a core compete for it. Each loop has its own listening socket. The sockets share the port through `SO_REUSEPORT`. A connection stays on one loop for its whole life.

Plain handlers run on a worker pool (`max(4, cores)` unless you set it, or unless a blocking pool is larger). Workers never touch an `h2o_req_t`. A `Task` runs on the loop. A completion whose request is already gone, because the client disconnected or the deadline already produced a 504, is dropped.

h2o is pinned to a master commit in `cmake/h2o.cmake`, because it has had no release tag since 2.2.6 (2019). The pin this guide was checked against is `8c95f068` (2026-10-24).

## Versions

crocket uses semantic versioning. While it is on 0.x, a minor bump may break the API, and patch releases are fixes and additions only. 1.0 is not released. There is no compatibility shim. For each minor you cross, read that version's changelog and rebuild.

| Channel | Git ref | For |
|---|---|---|
| stable | the latest `X.Y.Z` tag, now `@release@` | Everyone |
| latest | `main` | Trying what's next |
| experimental | `X.Y.Z-rc.N` | Testing risky changes |

The version is in `<crocket/version.hpp>`: `crocket::version::string` (`"@release@"`), and `commit` from git at configure time or from `-DCROCKET_GIT_COMMIT`.

The release notes are the [changelog](https://github.com/sean3z/crocket/blob/@release@/CHANGELOG.md). What's planned on the way to 1.0, including features not in crocket yet, is [issue 37](https://github.com/sean3z/crocket/issues/37).
