#include "collector.hpp"

#include <regex>

namespace ql {

bool is_safe_select(const std::string &sql) {
  std::string s = std::regex_replace(sql, std::regex(R"(/\*.*?\*/)"), " ");
  s = std::regex_replace(s, std::regex(R"(--[^\n]*)"), " ");

  std::regex start_re(R"(^\s*(select|with)\b)", std::regex::icase);
  std::regex dangerous_re(
      R"(\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|vacuum)\b)",
      std::regex::icase);

  if (!std::regex_search(s, start_re)) return false;
  if (std::regex_search(s, dangerous_re)) return false;
  return true;
}

} // namespace ql
