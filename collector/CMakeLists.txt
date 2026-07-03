cmake_minimum_required(VERSION 3.20)
project(plantrace_collector CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Protobuf REQUIRED)
find_package(OpenSSL REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(PQXX REQUIRED libpqxx)
pkg_check_modules(RDKAFKA REQUIRED rdkafka++)

set(PROTO_FILE ${CMAKE_CURRENT_SOURCE_DIR}/proto/telemetry.proto)
protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILE})

add_executable(plantrace-collector
  src/main.cpp
  src/sql_normalizer.cpp
  src/vector_detector.cpp
  src/safety.cpp
  src/fingerprint.cpp
  src/explain.cpp
  ${PROTO_SRCS}
)

target_include_directories(plantrace-collector PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${CMAKE_CURRENT_BINARY_DIR}
  ${PQXX_INCLUDE_DIRS}
  ${RDKAFKA_INCLUDE_DIRS}
)

target_link_libraries(plantrace-collector PRIVATE
  ${PQXX_LIBRARIES}
  ${RDKAFKA_LIBRARIES}
  OpenSSL::Crypto
  protobuf::libprotobuf
)

target_compile_options(plantrace-collector PRIVATE -Wall -Wextra -Wpedantic)

enable_testing()
add_test(NAME collector_help COMMAND plantrace-collector --help)
