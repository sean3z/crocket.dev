# Quickstart

A small program you can build once GCC 16.2 is on your `PATH`. The [getting started](/guide/v0.5/getting-started/) page covers the toolchain, Docker, and why the distro `g++-16` package is not enough.

## CMake

`@release@` is the current stable release.

```cmake
cmake_minimum_required(VERSION 3.28)
project(hello_app CXX)

include(FetchContent)
FetchContent_Declare(crocket
  GIT_REPOSITORY https://github.com/sean3z/crocket.git
  GIT_TAG @release@)
FetchContent_MakeAvailable(crocket)

add_executable(hello_app main.cpp)
target_link_libraries(hello_app PRIVATE crocket::crocket)
```

Linking `crocket::crocket` adds `-std=c++26` and `-freflection`. You don't set the standard yourself. crocket's examples and tests are not built, and h2o stays out of your headers.

## The program

```cpp
#include <crocket/crocket.hpp>

#include <string>
#include <string_view>

using namespace crocket;

namespace api {

[[= http::get("/hello/{name}")]]
auto hello(std::string_view name) -> std::string {
  return "Hello, " + std::string(name) + "!\n";
}

}  // namespace api

auto main() -> int {
  return build(Config::from_env())
      .attach(Logger{})
      .mount("/", reflect_routes<^^api>())
      .launch();
}
```

## Build and run

```sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=g++-16.2
cmake --build build
./build/hello_app
curl localhost:8000/hello/Ada
```

The release profile listens on `0.0.0.0:8000`. `CROCKET_PORT` changes the port. The first configure downloads h2o (about a 7 MB tarball) unless you point `FETCHCONTENT_SOURCE_DIR_H2O` at a checkout.

The binary needs GCC 16.2's `libstdc++`. If the loader says `GLIBCXX_3.4.35 not found`, point `LD_LIBRARY_PATH` at that GCC's `lib64`, or pass `-Wl,-rpath` to it.

`GET /healthz` is already there. It answers 200 `{"status":"ok"}` while the process is serving.
