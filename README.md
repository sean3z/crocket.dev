# crocket.dev

The source for [crocket.dev](https://crocket.dev). It is the landing page, the guide, and the migration pages, served by [crocket](https://github.com/sean3z/crocket) itself.

`GET /` is a route. It picks one rival for the benchmark block and sends `Cache-Control: no-cache`, so a refresh can show a different comparison. CSS and script URLs carry a content hash. HTML stays `no-cache`. The content security policy is `default-src 'self'`: no inline script, no inline style, no third-party host. `GET /healthz` is crocket's built-in liveness route.

crocket is pinned to the [0.5.2](https://github.com/sean3z/crocket/releases/tag/0.5.2) release, which includes static file serving.

The app listens on port **8100**. `CROCKET_PORT` still overrides it. That variable belongs to the framework. This site adds none of its own.

## Where things live

Guide prose is markdown in `guide/v0.5/`. The Express and Spring pages are `guide/v0.5/migrate-express.md` and `guide/v0.5/migrate-spring.md`.

The crocket examples live right in the markdown, and the `/ai/` example is in `web/ai/index.html`. Edit them in place.

`tools/build_guide.py` renders the guide, fingerprints CSS and JS, and writes `web/llms-full.txt`, `web/guide/`, `src/hashed/`, and `src/guide_assets.cpp`.

## Build locally

You need Python 3 for the guide, and GCC 16.2 for the binary. The toolchain image is `ghcr.io/sean3z/crocket-toolchain:gcc-16.2`. You don't have to install that compiler on the host if you build in Docker.

```sh
python3 tools/build_guide.py
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER=g++-16.2
cmake --build build --target crocket-site
```

A static preview of the rendered pages is `python3 -m http.server 8766 --directory web`.

## Deploy

Docker 29 with the classic builder. BuildKit and buildx are not required.

```sh
./deploy/deploy.sh
curl -i http://127.0.0.1:8100/
curl -i http://127.0.0.1:8100/healthz
```

`deploy/deploy.sh` exports `DOCKER_BUILDKIT=0`, builds the image, starts compose, and waits until `/healthz` returns. Compose publishes only `127.0.0.1:8100:8100`. The image build fetches crocket and h2o from GitHub.

On the Ubuntu 24.04 VPS, nginx terminates TLS and proxies to that loopback port. Install `deploy/nginx-crocket.dev.conf` where nginx includes site files, then reload nginx. Certificates are read from `/etc/letsencrypt/live/crocket.dev/`. The certificate needs both `crocket.dev` and `www.crocket.dev`, because `www` answers on 443 only long enough to 301 to `https://crocket.dev`.

Port 80 for either name redirects to `https://crocket.dev`. The proxy sets `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-Port`. The process trusts loopback and the private ranges, so those forwarded headers are used when the peer is nginx or the docker bridge, and ignored otherwise. `CROCKET_ALLOWED_HOSTS` can replace the default host list (`crocket.dev`, `localhost`, `127.0.0.1`).
