#pragma once
// Generated guide pages, filled in by tools/build_guide.py.

#include <crocket/crocket.hpp>

#include <string>
#include <vector>

namespace site_assets {

void add_guide(std::vector<crocket::Asset>& assets, std::vector<crocket::HeaderRule>& headers,
               const std::string& csp);

}  // namespace site_assets
