// The listen example on the Express and Spring Boot migration pages.
// Config::from_env() is the call at commit 9b446f8. launch() serves.

#include <crocket/crocket.hpp>

using namespace crocket;

int main() {
  return build(Config::from_env())
      .launch();
}
