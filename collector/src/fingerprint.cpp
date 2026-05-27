#include "collector.hpp"

#include <openssl/sha.h>
#include <iomanip>
#include <sstream>

namespace ql {

std::string sha256_hex(const std::string &input) {
  unsigned char digest[SHA256_DIGEST_LENGTH];
  SHA256(reinterpret_cast<const unsigned char *>(input.c_str()), input.size(), digest);
  std::ostringstream oss;
  for (unsigned char i : digest) {
    oss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(i);
  }
  return oss.str();
}

} // namespace ql
