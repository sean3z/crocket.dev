// The crocket column of the Express and Spring Boot migration pages.
// Both guides quote this file. checks/snippets/check_quotes.py keeps them honest.

#include <crocket/crocket.hpp>
#include <crocket/auth.hpp>

#include <cassert>
#include <format>
#include <iostream>
#include <optional>
#include <string>
#include <string_view>

using namespace crocket;

struct User {
  int id = 0;
  std::string email;
  std::optional<std::string> name;
};

namespace api {

[[= http::get("/users/{id}")]]
auto user_by_id(int id) -> Result<User> {
  if (id != 1) {
    return std::unexpected(
        ApiError::not_found(
            "no such user"));
  }
  return User{
      1, "ada@example.com", "Ada"};
}

struct Search {
  int page = 1;
  std::optional<std::string> q;
};

[[= http::get("/search")]]
auto search(Query<Search> query)
    -> Search {
  return *query;
}

struct NewUser {
  [[= json::email,
      = json::max_len(254)]]
  std::string email;
  std::optional<std::string> name;
};

[[= http::post("/users")]]
auto create(Json<NewUser> body)
    -> Created<User> {
  User user{1, body->email, body->name};
  return {user, "/users/1"};
}

[[= http::post("/users/{id}/archive")]]
auto archive(int id) -> Status<User> {
  return Status<User>{200, User{
      id, "ada@example.com", "Ada"}};
}

[[= http::get("/admin"),
    = auth::require("admin")]]
auto admin(Auth<> who) -> std::string {
  return std::format(
      "hello {}\n", who.subject);
}

}  // namespace api

struct AppHeader {
  void on_response(
      const Request&, Response& rs) {
    rs.headers.set("x-app", "users");
  }
};

Crocket make_app() {
  Config cfg;
  cfg.server.port = 8080;
  return build(cfg)
      .manage(auth::Jwt{
          .issuer =
              "https://login.example.com/",
          .audience = "users",
          .jwks =
              "https://login.example.com/"
              ".well-known/jwks.json",
      })
      .attach(Logger{})
      .attach(Metrics{})
      .attach(AppHeader{})
      .attach(OpenApi{{
          .title = "Users",
          .version = "1.0.0"}})
      .attach(Cors::allow_origins({"https://app.example.com"}))
      .mount("/", reflect_routes<^^api>())
      .mount("/assets",
          files{.root = "public"});
}

int main(int argc, char** argv) {
  Crocket app = make_app();
  if (argc > 1 && std::string_view(argv[1]) == "--check") {
    LocalClient client(app);
    auto created = client.post("/users")
                       .json("{\"email\":"
                             "\"ada@example.com\","
                             "\"name\":\"Ada\"}")
                       .dispatch();
    assert(created.status == 201);
    auto missing = client.get("/users/9")
                       .dispatch();
    assert(missing.status == 404);
    auto show = [](const char* name, const Response& rs) {
      std::cout << name << " " << rs.status << "\n" << rs.body << "\n";
      if (auto loc = rs.headers.get("location")) std::cout << "location " << *loc << "\n";
    };
    show("create", created);
    auto bad_email = client.post("/users").json(R"({"email":"not-an-email"})").dispatch();
    show("bad_email", bad_email);
    auto no_name = client.post("/users").json(R"({"email":"ada@example.com"})").dispatch();
    show("no_name", no_name);
    show("missing", missing);
    auto nope = client.get("/users/nope").dispatch();
    show("nope", nope);
    auto found = client.get("/search?page=2&q=ada").dispatch();
    show("search", found);
    auto def = client.get("/search").dispatch();
    show("search_default", def);
    auto bad_page = client.get("/search?page=nope").dispatch();
    show("search_bad", bad_page);
    auto archived = client.post("/users/1/archive").dispatch();
    show("archive", archived);
    return created.status == 201 && missing.status == 404 ? 0 : 1;
  }
  return app.launch();
}
