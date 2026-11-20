# crocket.dev

The landing page for [crocket](https://github.com/sean3z/crocket), served by crocket itself.

The HTML, CSS, and script are `#embed`'d into one binary and mounted with `crocket::files`. HTML responses carry a content security policy that allows only this origin: no inline script, no inline style, no third-party host. `GET /healthz` is crocket's built-in liveness route.

crocket is pinned to commit `9b446f8c2423262ef1cbf3afe370a0ae2f81d181` (static file serving). The latest release is [0.5.1](https://github.com/sean3z/crocket/releases/tag/0.5.1). Static files are unreleased in that tag, which is why the pin is a commit and not `0.5.1`.

The app listens on port **8100** (`CROCKET_PORT` still overrides it; that variable belongs to the framework). There are no application environment variables.

The guide is markdown in `guide/v0.5/`. `tools/build_guide.py` renders it to HTML, highlights code, and writes `src/guide_assets.cpp`, which `#embed`s the pages. CMake runs that script before it compiles. The pages are served by `crocket::files` with the same content security policy as the landing page.

## Run

Docker 29 with the classic builder. BuildKit and buildx are not required.

```sh
./deploy/deploy.sh
curl -i http://127.0.0.1:8100/
curl -i http://127.0.0.1:8100/healthz
```

`deploy/deploy.sh` exports `DOCKER_BUILDKIT=0`, builds the image, starts compose, and waits until `/healthz` returns. Compose publishes only `127.0.0.1:8100:8100`.

The image build fetches crocket and h2o from GitHub. The compiler is GCC 16.2 inside `ghcr.io/sean3z/crocket-toolchain:gcc-16.2`. You don't install that compiler on the host.

## Deploy

On the Ubuntu 24.04 VPS, nginx terminates TLS and proxies to the loopback port. Install `deploy/nginx-crocket.dev.conf` where nginx includes site files, then reload nginx. Certificates are read from `/etc/letsencrypt/live/crocket.dev/`. The certificate needs both `crocket.dev` and `www.crocket.dev` on it, because `www` answers on 443 only long enough to 301 to `https://crocket.dev`.

Port 80 for either name redirects to `https://crocket.dev`. The proxy sets `Host`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-Port`.

The process trusts loopback and the private ranges, so those forwarded headers are used when the peer is nginx or the docker bridge, and ignored otherwise. `CROCKET_ALLOWED_HOSTS` can replace the default host list (`crocket.dev`, `localhost`, `127.0.0.1`).

## What this build measured

On a 4-core machine the release process starts 4 event loops and 4 workers. After it was idle:

- Image size: 176 MB (`docker images`). Ubuntu 26.04 is almost all of that. The stripped `crocket-site` binary is 1.6 MB, and GCC 16.2's `libstdc++` plus `libgcc_s` add about 3.6 MB.
- Idle RSS: 11.2 MiB (`VmRSS` 11460 kB). About 1.5 MiB of that is anonymous (`RssAnon` 1584 kB). The rest is file-backed libraries.

Those numbers are this program on this machine, not a crocket benchmark. The framework's own bench results are not in its git tree.
