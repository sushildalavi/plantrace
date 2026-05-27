from prometheus_client import Counter, Gauge, Histogram

telemetry_events_consumed_total = Counter(
    "querylens_telemetry_events_consumed_total",
    "Total telemetry events consumed from Kafka",
)
telemetry_persist_failures_total = Counter(
    "querylens_telemetry_persist_failures_total",
    "Failed telemetry persistence attempts",
)
failed_explain_captures_total = Counter(
    "querylens_failed_explain_captures_total",
    "Number of telemetry events missing explain payload",
)
regression_events_total = Counter(
    "querylens_regression_events_total",
    "Regression events created",
    labelnames=("severity", "regression_type"),
)
collector_heartbeat_age_seconds = Gauge(
    "querylens_collector_heartbeat_age_seconds",
    "Age of latest collector heartbeat",
    labelnames=("service_id", "environment"),
)
kafka_consumer_lag = Gauge(
    "querylens_kafka_consumer_lag",
    "Kafka consumer lag estimate",
    labelnames=("topic",),
)
api_request_latency_seconds = Histogram(
    "querylens_api_request_latency_seconds",
    "HTTP request latency",
    labelnames=("path", "method", "status"),
)
