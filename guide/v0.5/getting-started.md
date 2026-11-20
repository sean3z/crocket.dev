# Getting started

The quickstart assumes the compiler is already installed. This page is the part that usually takes the time.

## What you need

- GCC 16.2 or later, with `-freflection`. Clang is not tested.
- CMake 3.28 or later, and Ninja or Make.
- OpenSSL and zlib development headers (`libssl-dev`, `zlib1g-dev`), and `perl`, which h2o's build runs.
- Network access on the first configure, to fetch h2o. Set `FETCHCONTENT_SOURCE_DIR_H2O` to a local checkout to build offline.

There are no `install()` rules yet, so `find_package(crocket)` does not work. Use FetchContent, as the [quickstart](/guide/v0.5/quickstart/) does.

## GCC 16.2

Ubuntu 26.04's `g++-16` package is a pre-release snapshot (`16-20260322`). Its reflection bugs break a translation unit that mounts routes. The errors start with `accessing uninitialized member 'crocket::detail::Binding::kind'`.

The toolchain crocket is developed with is GCC 16.2 on Ubuntu 26.04. `./dev gcc` builds that compiler into `~/.local/gcc-16.2`. CI uses the image `ghcr.io/sean3z/crocket-toolchain:gcc-16.2`, which already has it.

## Try it without a toolchain

The hello image listens on port 8000:

```sh
docker run --rm -p 8000:8000 ghcr.io/sean3z/crocket-hello:stable
curl localhost:8000/hello/Rocketeer/42
```

That prints `Hello, 42 year old named Rocketeer!`. Pin `:0.5.1` when you deploy it. `:stable` tracks the stable release. `:latest` tracks `main`.

The same route, compiled in the browser, is on [Compiler Explorer](https://godbolt.org/z/Gdes8Kbdq) (GCC 16.2, `-std=c++26 -freflection`). That sketch is `examples/godbolt.cpp`. It has no h2o.

To work on an app inside the toolchain image:

```sh
docker run --rm -it -v "$PWD:/src" -p 8000:8000 ghcr.io/sean3z/crocket-toolchain:gcc-16.2
```

`./dev run` uses the dev profile, which listens on `127.0.0.1`. Inside a container, build the release tree and run the binary if you need `0.0.0.0`.

## Dev profile

`CROCKET_PROFILE=dev` is for your own machine. Compared with the release defaults it:

- Puts `ApiError::detail` in error bodies, including an uncaught exception's `what()`. Release never sends that.
- Writes readable log lines, colored on a terminal unless `NO_COLOR` is set.
- Prints every route at launch, and turns on `GET /__routes`.
- Uses a one-hour request deadline and a one-second drain.
- Binds `127.0.0.1` when `server.host` is empty, instead of `0.0.0.0`.

Anything other than `dev` or `release` (or unset, which means release) throws `std::invalid_argument` at startup.

The next page is the [overview](/guide/v0.5/overview/) of the handler model.
