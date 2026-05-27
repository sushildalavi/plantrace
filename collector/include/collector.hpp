#pragma once

#include <optional>
#include <string>

namespace ql {

struct QueryRow {
  std::string query;
  long long calls{0};
  double total_exec_time_ms{0.0};
  double mean_exec_time_ms{0.0};
  long long rows{0};
  long long shared_blks_hit{0};
  long long shared_blks_read{0};
  long long temp_blks_read{0};
  long long temp_blks_written{0};
};

std::string normalize_sql(const std::string &sql);
std::string sha256_hex(const std::string &input);
bool is_safe_select(const std::string &sql);
std::string detect_vector_operator(const std::string &sql);
std::optional<std::string> run_explain_json(
    const std::string &conn_str,
    const std::string &sql,
    int timeout_ms);

} // namespace ql
