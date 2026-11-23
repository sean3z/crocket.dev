// The listen example on the Express and Spring Boot migration pages.
// Config::from_env() then launch().

#include <crocket/crocket.hpp>

using namespace crocket;

auto main() -> int {
  return build(Config::from_env())
      .launch();
}
