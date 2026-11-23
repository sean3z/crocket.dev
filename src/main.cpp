// The crocket.dev site. The homepage is a route so each GET / can name a
// different rival. Guide pages, CSS, and script are #embed'd files.
// CROCKET_* variables still belong to the framework (Config::from_env).

#include <crocket/crocket.hpp>
#include "guide_assets.hpp"

#include <atomic>
#include <string>
#include <string_view>
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
static constexpr unsigned char teapot_html[] = {
#embed "../web/teapot.html"
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
static constexpr unsigned char ai_html[] = {
#embed "../web/ai/index.html"
};
static constexpr unsigned char ai_js[] = {
#embed "../web/ai/exchange.js"
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

// Figures are the ones printed in "Where the cycles go" for the Heroes CRUD
// rig: crocket 35.2k req/s and 21 MB peak, against one rival per response.
// Rocket's peak is 22 MB, so that line is "vs 22 MB" with no extra claim.
struct Rival {
  std::string_view id;
  std::string_view rate;    // already includes "vs "
  std::string_view memory;  // already includes "vs "
  std::string_view note;    // empty when the post has no short caveat
};

constexpr Rival kRivals[] = {
    {"rocket", "vs Rocket's 17.4k", "vs 22 MB", ""},
    {"spring", "vs Spring Boot's 8.4k", "vs Spring Boot's 471 MB", "JVM ran untuned."},
    {"node", "vs Node.js (Fastify)'s 6.6k", "vs Node.js (Fastify)'s 216 MB", "Single Node process."},
};

const Rival& rival_for(const Request& rq) {
  if (auto asked = rq.query_param("vs")) {
    for (const auto& rival : kRivals)
      if (rival.id == *asked) return rival;
  }
  // One process, so a refresh moves to the next rival. No cookie.
  static std::atomic<unsigned> next{0};
  auto i = next.fetch_add(1, std::memory_order_relaxed);
  return kRivals[i % (sizeof kRivals / sizeof kRivals[0])];
}

std::string numbers_html(const Rival& rival) {
  std::string html;
  html.reserve(640);
  html += R"(<div class="numbers">
          <article class="stat">
            <p class="stat-value">35.2k <span>req/s</span></p>
            <p class="stat-vs">)";
  html += rival.rate;
  html += R"(</p>
            <p class="stat-caption">Heroes CRUD, max throughput.</p>
          </article>
          <article class="stat">
            <p class="stat-value">21 <span>MB</span></p>
            <p class="stat-vs">)";
  html += rival.memory;
  html += R"(</p>
            <p class="stat-caption">Heroes CRUD, peak memory.</p>
          </article>
        </div>)";
  if (!rival.note.empty()) {
    html += R"(
        <p class="stat-note">)";
    html += rival.note;
    html += "</p>";
  }
  return html;
}

// The markers bracket the Rocket copy in index.html. A request replaces that
// span, so the page does not need script to show a different rival.
std::string render_home(const Rival& rival) {
  const std::string_view page(reinterpret_cast<const char*>(index_html), sizeof index_html);
  constexpr std::string_view open = "<!--rival-->";
  constexpr std::string_view close = "<!--/rival-->";
  const auto begin = page.find(open);
  const auto end = page.find(close);
  const auto block = numbers_html(rival);
  if (begin == std::string_view::npos || end == std::string_view::npos || end < begin)
    return std::string(page);
  std::string out;
  out.reserve(page.size() + block.size());
  out.append(page.substr(0, begin));
  out.append(block);
  out.append(page.substr(end + close.size()));
  return out;
}

Response homepage(const Request& rq) {
  Response rs;
  rs.body = render_home(rival_for(rq));
  rs.set_content_type("text/html; charset=utf-8");
  rs.headers.set("content-security-policy", kCsp);
  rs.headers.set("cache-control", "no-cache");
  return rs;
}

files site_files() {
  files web;
  // index.html is served by pages::home, so a refresh can change the rival.
  web.assets = {
      asset("style.css", style_css),
      asset("theme.js", theme_js),
      asset("favicon.svg", favicon_svg),
      asset("ai/index.html", ai_html),
      asset("ai/exchange.js", ai_js),
  };
  web.cache = {
      {"*.html", "no-cache"},
      {"ai/*.html", "no-cache"},
      {"ai/*.js", "public, max-age=3600"},
      {"*.css", "public, max-age=3600"},
      {"*.js", "public, max-age=3600"},
      {"*.svg", "public, max-age=86400"},
  };
  web.headers = {
      {"*.html", {{"content-security-policy", kCsp}}},
      {"ai/*.html", {{"content-security-policy", kCsp}}},
  };
  // Nested guide pages need their own globs: * does not cross '/'.
  site_assets::add_guide(web.assets, web.headers, kCsp);
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

namespace pages {

[[= http::get("/")]]
auto home(const Request& rq) -> Response { return homepage(rq); }

// HEAD falls back to this GET and drops the body. No Teapot alias at this pin.
[[= http::get("/teapot")]]
auto teapot() -> WithStatus<418, Response> {
  Response rs;
  rs.set_content_type("text/html; charset=utf-8");
  rs.headers.set("content-security-policy", kCsp);
  rs.headers.set("cache-control", "no-cache");
  rs.body.assign(reinterpret_cast<const char*>(teapot_html), sizeof teapot_html);
  return {std::move(rs)};
}

}  // namespace pages

int main() {
  // /healthz and /readyz are built in. Routes match before files, so GET /
  // is the homepage above and everything else is still a static file.
  return build(site_config())
      .attach(Logger{})
      .attach(HtmlNotFound{})
      .mount("/", reflect_routes<^^pages>())
      .mount("/", site_files())
      .launch();
}
