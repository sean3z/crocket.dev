// The crocket.dev site. Pages are #embed'd and served by crocket::files.
// CROCKET_* variables still belong to the framework (Config::from_env).

#include <crocket/crocket.hpp>

#include <string>
#include <utility>

using namespace crocket;

namespace {

// Replaces Shield's default (default-src 'none') on HTML. No inline script or
// style, and no host but this one. Shield leaves a header the response already
// has, which is why files.headers can set this for *.html.
constexpr char kCsp[] =
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self'; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "base-uri 'none'; "
    "form-action 'none'; "
    "object-src 'none'; "
    "frame-ancestors 'none'";

static constexpr unsigned char index_html[] = {
#embed "../web/index.html"
};
static constexpr unsigned char not_found_html[] = {
#embed "../web/404.html"
};
static constexpr unsigned char style_css[] = {
#embed "../web/style.css"
};
static constexpr unsigned char theme_js[] = {
#embed "../web/theme.js"
};
static constexpr unsigned char favicon_svg[] = {
#embed "../web/favicon.svg"
};

// A browser navigation asks for HTML. Other 404s (a missing favicon, curl with
// no Accept) keep crocket's problem+json body.
struct HtmlNotFound {
  void on_response(const Request& rq, Response& rs) {
    if (rs.status != 404) return;
    if (!rq.header("accept").value_or("").contains("html")) return;
    rs.body.assign(reinterpret_cast<const char*>(not_found_html), sizeof not_found_html);
    rs.set_content_type("text/html; charset=utf-8");
    rs.headers.set("content-security-policy", kCsp);
    rs.headers.set("cache-control", "no-cache");
  }
};

files site_files() {
  files web;
  web.assets = {
      asset("index.html", index_html),
      asset("style.css", style_css),
      asset("theme.js", theme_js),
      asset("favicon.svg", favicon_svg),
  };
  web.cache = {
      {"*.html", "no-cache"},
      {"*.css", "public, max-age=3600"},
      {"*.js", "public, max-age=3600"},
      {"*.svg", "public, max-age=86400"},
  };
  web.headers = {{"*.html", {{"content-security-policy", kCsp}}}};
  return web;
}

Config site_config() {
  // 8100 is this program's default. CROCKET_PORT and CROCKET_LISTEN still win.
  Config base;
  base.server.port = 8100;
  // nginx on the VPS (and the docker bridge in front of it) may send
  // X-Forwarded-For. Anyone else is ignored.
  base.proxy.trusted = {"127.0.0.1", "::1", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"};
  base.proxy.allowed_hosts = {"crocket.dev", "localhost", "127.0.0.1"};
  return Config::from_env(std::move(base));
}

}  // namespace

int main() {
  // /healthz and /readyz are built in. Routes match before files.
  return build(site_config())
      .attach(Logger{})
      .attach(HtmlNotFound{})
      .mount("/", site_files())
      .launch();
}
