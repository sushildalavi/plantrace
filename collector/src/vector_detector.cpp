#include "collector.hpp"

namespace ql {

std::string detect_vector_operator(const std::string &sql) {  if (sql.find("<=>") != std::string::npos) return "<=>";
  if (sql.find("<->") != std::string::npos) return "<->";
  if (sql.find("<#>") != std::string::npos) return "<#>";
  return "";
}

} // namespace ql
