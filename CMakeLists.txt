cmake_minimum_required(VERSION 3.28)
project(crocket_site LANGUAGES C CXX)

# crocket.dev. The framework pin is the one line in VERSION. Its examples
# and tests stay out of this build (crocket is not the top-level project).
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/VERSION" CROCKET_RELEASE)
string(STRIP "${CROCKET_RELEASE}" CROCKET_RELEASE)
if(NOT CROCKET_RELEASE MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+$")
  message(FATAL_ERROR "VERSION must be one X.Y.Z release, got '${CROCKET_RELEASE}'")
endif()
set(CMAKE_CXX_STANDARD 26)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_CXX_SCAN_FOR_MODULES OFF)

include(FetchContent)
FetchContent_Declare(crocket
  GIT_REPOSITORY https://github.com/sean3z/crocket.git
  GIT_TAG ${CROCKET_RELEASE}
  GIT_SHALLOW OFF)
set(CROCKET_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(CROCKET_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(CROCKET_PG OFF CACHE STRING "" FORCE)
# The site binary doesn't link auth or the HTTP client.
set(CROCKET_CLIENT OFF CACHE STRING "" FORCE)
set(CROCKET_AUTH OFF CACHE STRING "" FORCE)
FetchContent_MakeAvailable(crocket)

# h2o is already built with function sections. These let --gc-sections drop
# unused crocket object code too. About 300 KB of unused h2o falls out at link.
if(TARGET crocket)
  target_compile_options(crocket PRIVATE -ffunction-sections -fdata-sections)
endif()

file(GLOB GUIDE_MD CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/guide/v0.5/*.md")
set(GUIDE_CPP "${CMAKE_CURRENT_SOURCE_DIR}/src/guide_assets.cpp")
set(LLMS_FULL "${CMAKE_CURRENT_SOURCE_DIR}/web/llms-full.txt")
set(HASHED_LLMS "${CMAKE_CURRENT_SOURCE_DIR}/src/hashed/llms.txt")
set(HASHED_HTML
  "${CMAKE_CURRENT_SOURCE_DIR}/src/hashed/index.html"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/hashed/404.html"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/hashed/teapot.html"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/hashed/ai/index.html"
  "${CMAKE_CURRENT_SOURCE_DIR}/src/hashed/benchmarks/index.html")
add_custom_command(
    OUTPUT "${GUIDE_CPP}" "${LLMS_FULL}" "${HASHED_LLMS}" ${HASHED_HTML}
    COMMAND bash -c "python3 tools/build_guide.py || { test -s web/llms-full.txt && test -s src/guide_assets.cpp && test -s src/hashed/llms.txt && test -s src/hashed/index.html && test -s src/hashed/404.html && test -s src/hashed/teapot.html && test -s src/hashed/ai/index.html && test -s src/hashed/benchmarks/index.html; }"
    DEPENDS
      "${CMAKE_CURRENT_SOURCE_DIR}/VERSION"
      "${CMAKE_CURRENT_SOURCE_DIR}/tools/build_guide.py"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/llms.txt"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/style.css"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/theme.js"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/ai/exchange.js"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/index.html"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/404.html"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/teapot.html"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/ai/index.html"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/benchmarks/index.html"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/benchmarks/bench.css"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/benchmarks/render.js"
      "${CMAKE_CURRENT_SOURCE_DIR}/web/benchmarks/data.json"
      "${CMAKE_CURRENT_SOURCE_DIR}/data/parity-sizes.json"
      "${CMAKE_CURRENT_SOURCE_DIR}/data/benchmarks.json"
      ${GUIDE_MD}
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    COMMENT "Rendering the crocket guide"
    VERBATIM)

add_executable(crocket-site src/main.cpp "${GUIDE_CPP}")
set_source_files_properties(src/main.cpp PROPERTIES OBJECT_DEPENDS "${LLMS_FULL};${HASHED_LLMS};${HASHED_HTML}")
target_link_libraries(crocket-site PRIVATE crocket::crocket)
target_compile_options(crocket-site PRIVATE -Wall -Wextra -ffunction-sections -fdata-sections)
target_link_options(crocket-site PRIVATE
  "LINKER:--gc-sections"
  "LINKER:--as-needed"
  "LINKER:-rpath,/usr/local/lib/crocket")

