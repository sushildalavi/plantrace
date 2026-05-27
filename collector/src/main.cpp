#include "collector.hpp"
#include "telemetry.pb.h"

#include <chrono>
#include <cstdlib>
#include <ctime>
#include <iostream>
#include <memory>
#include <pqxx/pqxx>
#include <rdkafkacpp.h>
#include <sstream>

namespace {

std::string env_or(const char *k, const std::string &d) {
  const char *v = std::getenv(k);
  return v ? std::string(v) : d;
}

int env_int(const char *k, int d) {
  const char *v = std::getenv(k);
  if (!v) return d;
  return std::atoi(v);
}

std::string utc_now_iso() {
  std::time_t now = std::time(nullptr);
  char buf[32];
  std::strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", std::gmtime(&now));
  return buf;
}

std::vector<ql::QueryRow> read_pg_stat(const std::string &conn_str, double min_mean_ms) {
  std::vector<ql::QueryRow> out;
  pqxx::connection c(conn_str);
  pqxx::read_transaction tx(c);
  pqxx::result r = tx.exec_params(
      R"(
SELECT query, calls, total_exec_time, mean_exec_time, rows,
       shared_blks_hit, shared_blks_read, temp_blks_read, temp_blks_written
FROM pg_stat_statements
WHERE query NOT ILIKE '%pg_stat_statements%'
  AND query NOT ILIKE '%querylens.%'
  AND mean_exec_time >= $1
ORDER BY mean_exec_time DESC
)",
      min_mean_ms);

  for (const auto &row : r) {
    ql::QueryRow qr;
    qr.query = row["query"].c_str();
    qr.calls = row["calls"].as<long long>(0);
    qr.total_exec_time_ms = row["total_exec_time"].as<double>(0.0);
    qr.mean_exec_time_ms = row["mean_exec_time"].as<double>(0.0);
    qr.rows = row["rows"].as<long long>(0);
    qr.shared_blks_hit = row["shared_blks_hit"].as<long long>(0);
    qr.shared_blks_read = row["shared_blks_read"].as<long long>(0);
    qr.temp_blks_read = row["temp_blks_read"].as<long long>(0);
    qr.temp_blks_written = row["temp_blks_written"].as<long long>(0);
    out.push_back(qr);
  }
  return out;
}

void print_help() {
  std::cout << "querylens-collector options via env vars:\n"
            << "COLLECTOR_DSN, COLLECTOR_ENVIRONMENT, COLLECTOR_SERVICE_ID,\n"
            << "COLLECTOR_MIN_MEAN_MS, COLLECTOR_EXPLAIN_TIMEOUT_MS,\n"
            << "COLLECTOR_STDOUT_MODE, KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC_QUERY_TELEMETRY\n";
}

} // namespace

int main(int argc, char **argv) {
  if (argc > 1 && (std::string(argv[1]) == "--help" || std::string(argv[1]) == "-h")) {
    print_help();
    return 0;
  }

  GOOGLE_PROTOBUF_VERIFY_VERSION;

  const std::string dsn = env_or("COLLECTOR_DSN", "postgresql://querylens:querylens@db:5432/querylens");
  const std::string environment = env_or("COLLECTOR_ENVIRONMENT", "local");
  const std::string service_id = env_or("COLLECTOR_SERVICE_ID", "collector-cpp");
  const double min_mean_ms = std::stod(env_or("COLLECTOR_MIN_MEAN_MS", "0"));
  const int explain_timeout_ms = env_int("COLLECTOR_EXPLAIN_TIMEOUT_MS", 5000);
  const bool stdout_mode = env_or("COLLECTOR_STDOUT_MODE", "false") == "true";

  const std::string brokers = env_or("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092");
  const std::string topic = env_or("KAFKA_TOPIC_QUERY_TELEMETRY", "query-telemetry");

  std::string errstr;
  std::unique_ptr<RdKafka::Producer> producer;
  if (!stdout_mode) {
    auto conf = std::unique_ptr<RdKafka::Conf>(RdKafka::Conf::create(RdKafka::Conf::CONF_GLOBAL));
    conf->set("bootstrap.servers", brokers, errstr);
    producer.reset(RdKafka::Producer::create(conf.get(), errstr));
    if (!producer) {
      std::cerr << "failed to create kafka producer: " << errstr << "\n";
      return 1;
    }
  }

  try {
    auto rows = read_pg_stat(dsn, min_mean_ms);
    for (const auto &r : rows) {
      std::string norm = ql::normalize_sql(r.query);
      std::string fp = ql::sha256_hex(norm);
      std::string vec_op = ql::detect_vector_operator(norm);
      auto explain = ql::run_explain_json(dsn, r.query, explain_timeout_ms);

      querylens::telemetry::v1::QueryTelemetryEvent evt;
      evt.set_database_name("querylens");
      evt.set_environment(environment);
      evt.set_service_id(service_id);
      evt.set_query_fingerprint(fp);
      evt.set_normalized_sql(norm);
      evt.set_raw_query_sample(r.query.substr(0, 512));
      evt.set_calls(r.calls);
      evt.set_total_exec_time_ms(r.total_exec_time_ms);
      evt.set_mean_exec_time_ms(r.mean_exec_time_ms);
      evt.set_rows(r.rows);
      evt.set_shared_blks_hit(r.shared_blks_hit);
      evt.set_shared_blks_read(r.shared_blks_read);
      evt.set_temp_blks_read(r.temp_blks_read);
      evt.set_temp_blks_written(r.temp_blks_written);
      evt.set_detected_vector_operator(vec_op);
      evt.set_is_vector_query(!vec_op.empty());
      evt.set_explain_json(explain.value_or(""));
      evt.set_captured_at(utc_now_iso());

      std::string payload;
      evt.SerializeToString(&payload);
      std::string key = "querylens:" + environment + ":" + fp;

      if (stdout_mode) {
        std::cout << key << " " << evt.ShortDebugString() << "\n";
      } else {
        auto rc = producer->produce(topic, RdKafka::Topic::PARTITION_UA,
                                    RdKafka::Producer::RK_MSG_COPY,
                                    const_cast<char *>(payload.data()), payload.size(),
                                    &key, nullptr);
        if (rc != RdKafka::ERR_NO_ERROR) {
          std::cerr << "produce failed: " << RdKafka::err2str(rc) << "\n";
        }
      }
    }

    if (producer) {
      producer->flush(5000);
    }

    std::cerr << "collector processed rows=" << rows.size() << "\n";
  } catch (const std::exception &e) {
    std::cerr << "collector failed: " << e.what() << "\n";
    return 1;
  }

  google::protobuf::ShutdownProtobufLibrary();
  return 0;
}
