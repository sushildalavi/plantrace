#include "collector.hpp"

#include <algorithm>
#include <cctype>
#include <regex>

namespace ql {

std::string normalize_sql(const std::string &sql) {
  if (sql.empty()) return "";
  std::string s = std::regex_replace(sql, std::regex(R"(/\*.*?\*/)"), " ");
  s = std::regex_replace(s, std::regex(R"(--[^\n]*)"), " ");
  s = std::regex_replace(s, std::regex(R"('(?:''|[^'])*')"), "?");
  s = std::regex_replace(s, std::regex(R"(\$\d+)"), "?");
  s = std::regex_replace(s, std::regex(R"(\b\d+(?:\.\d+)?\b)"), "?");
  s = std::regex_replace(s, std::regex(R"(\s+)"), " ");

  while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back()))) s.pop_back();
  while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
  if (!s.empty() && s.back() == ';') {
    s.pop_back();
    while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back()))) s.pop_back();
  }

  std::transform(s.begin(), s.end(), s.begin(),
                 [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
  return s;
}

} // namespace ql
