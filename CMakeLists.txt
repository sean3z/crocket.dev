cmake_minimum_required(VERSION 3.28)
project(crocket_site LANGUAGES C CXX)

# crocket.dev. The framework is pinned to the static-files commit. Its examples
# and tests stay out of this build (crocket is not the top-level project).
set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)

include(FetchContent)
FetchContent_Declare(crocket
  GIT_REPOSITORY https://github.com/sean3z/crocket.git
  GIT_TAG 9b446f8c2423262ef1cbf3afe370a0ae2f81d181
  GIT_SHALLOW OFF)
set(CROCKET_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(CROCKET_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(CROCKET_PG OFF CACHE STRING "" FORCE)
set(CROCKET_CLIENT OFF CACHE STRING "" FORCE)
set(CROCKET_AUTH OFF CACHE STRING "" FORCE)
FetchContent_MakeAvailable(crocket)

# h2o is already built with function sections. These let --gc-sections drop
# unused crocket object code too. About 300 KB of unused h2o falls out at link.
if(TARGET crocket)
  target_compile_options(crocket PRIVATE -ffunction-sections -fdata-sections)
endif()

add_executable(crocket-site src/main.cpp)
target_link_libraries(crocket-site PRIVATE crocket::crocket)
target_compile_options(crocket-site PRIVATE -Wall -Wextra -ffunction-sections -fdata-sections)
target_link_options(crocket-site PRIVATE
  "LINKER:--gc-sections"
  "LINKER:--as-needed"
  "LINKER:-rpath,/usr/local/lib/crocket")
