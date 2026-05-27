#include "collector.hpp"

#include <pqxx/pqxx>

namespace ql {

std::optional<std::string> run_explain_json(
    const std::string &conn_str,
    const std::string &sql,
    int timeout_ms) {
  try {
    if (!is_safe_select(sql)) return std::nullopt;
    pqxx::connection c(conn_str);
    pqxx::work tx(c);
    tx.exec0("SET LOCAL statement_timeout = '" + tx.esc(std::to_string(timeout_ms)) + "ms'");
    auto r = tx.exec("EXPLAIN (FORMAT JSON) " + sql);
    tx.commit();
    if (r.empty() || r[0].empty()) return std::nullopt;
    return r[0][0].c_str();
  } catch (...) {
    return std::nullopt;
  }
}

} // namespace ql
