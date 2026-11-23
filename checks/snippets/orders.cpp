// The service shown on /ai/. The page quotes this file.
// --check prints a 422 and a 401 from the real pipeline.

#include <crocket/crocket.hpp>
#include <crocket/auth.hpp>

#include <iostream>
#include <optional>
#include <string>
#include <string_view>

using namespace crocket;

struct NewOrder {
  [[= json::min_len(1), = json::max_len(80)]] std::string sku;
  [[= json::min(1)]] int qty;
};

struct Order {
  int id = 0;
  std::string sku;
  int qty = 0;
};

namespace api {

[[= http::post("/orders")]]
auto create(Json<NewOrder> body) -> Created<Order> {
  return {Order{1, body->sku, body->qty}, "/orders/1"};
}

[[= http::get("/orders/{id}"), = auth::require("orders")]]
auto order(int id, [[maybe_unused]] Auth<> who) -> Result<Order> {
  if (id != 1) {
    return std::unexpected(
        ApiError::not_found("no such order"));
  }
  return Order{1, "WIDGET", 2};
}

}  // namespace api

Crocket make_app() {
  Config cfg;
  cfg.server.port = 8080;
  return build(cfg)
      .manage(auth::Jwt::oidc("https://login.example.com/", "orders"))
      .attach(Logger{})
      .attach(Metrics{})
      .attach(OpenApi{{.title = "Orders", .version = "1.0.0"}})
      .mount("/", reflect_routes<^^api>());
}

int main(int argc, char** argv) {
  Crocket app = make_app();
  if (argc > 1 && std::string_view(argv[1]) == "--check") {
    LocalClient client(app);
    auto bad = client.post("/orders").json(R"({"sku":"WIDGET","qty":0})").dispatch();
    std::cout << "POST " << bad.status << "\n" << bad.body << "\n";
    auto denied = client.get("/orders/1").dispatch();
    std::cout << "GET " << denied.status << "\n" << denied.body << "\n";
    auto metrics = client.get("/metrics").dispatch();
    std::cout << "METRICS " << metrics.status << "\n" << metrics.body << "\n";
    auto ready = client.get("/readyz").dispatch();
    std::cout << "READY " << ready.status << "\n" << ready.body << "\n";
    return 0;
  }
  return app.launch();
}
