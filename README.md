# crocket.dev

The source for [crocket.dev](https://crocket.dev). It is the landing page, the guide, and the migration pages, served by [crocket](https://github.com/sean3z/crocket) itself.

`GET /` is a route. It picks one rival for the benchmark block and sends `Cache-Control: no-cache`, so a refresh can show a different comparison. CSS and script URLs carry a content hash. HTML stays `no-cache`. The content security policy is `default-src 'self'`: no inline script, no inline style, no third-party host. `GET /healthz` is crocket's built-in liveness route.

crocket is pinned to the release in [`VERSION`](VERSION). That one line is the FetchContent tag, and `tools/build_guide.py` stamps it onto the guide, the badges, and the snippets. Guide URLs stay `/guide/v0.5/`. The pin includes static file serving.

The app listens on port **8100**. `CROCKET_PORT` still overrides it. That variable belongs to the framework. This site adds none of its own.

## Where things live

Guide prose is markdown in `guide/v0.5/`. The Express and Spring pages are `guide/v0.5/migrate-express.md` and `guide/v0.5/migrate-spring.md`. Where a page names the release, it says `@release@`, and the guide build fills that in from `VERSION`.

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

A static preview of the rendered pages, with the release filled in, is `python3 -m http.server 8766 --directory src/preview`.

