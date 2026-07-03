from prometheus_client import Counter, Gauge, Histogram

telemetry_events_consumed_total = Counter(
    "plantrace_telemetry_events_consumed_total",
    "Total telemetry events consumed from Kafka",
)
telemetry_persist_failures_total = Counter(
    "plantrace_telemetry_persist_failures_total",
    "Failed telemetry persistence attempts",
)
plantrace_persistence_failures_total = telemetry_persist_failures_total
duplicate_events_total = Counter(
    "plantrace_duplicate_events_total",
    "Duplicate telemetry events skipped by idempotency key",
)
ingest_retries_total = Counter(
    "plantrace_ingest_retries_total",
    "Number of ingestion retry attempts",
)
dlq_events_total = Counter(
    "plantrace_dlq_events_total",
    "Telemetry events routed to dead-letter queue",
)
failed_explain_captures_total = Counter(
    "plantrace_failed_explain_captures_total",
    "Number of telemetry events missing explain payload",
)
regression_events_total = Counter(
    "plantrace_regression_events_total",
    "Regression events created",
    labelnames=("severity", "regression_type"),
)
diagnostic_events_total = Counter(
    "plantrace_diagnostic_events_total",
    "Diagnostic findings created",
    labelnames=("severity", "diagnostic_type"),
)
diagnostic_failures_total = Counter(
    "plantrace_diagnostic_failures_total",
    "Diagnostic evaluation failures",
)
placement_failures_total = Counter(
    "plantrace_placement_failures_total",
    "Placement simulation failures",
)
collector_heartbeat_age_seconds = Gauge(
    "plantrace_collector_heartbeat_age_seconds",
    "Age of latest collector heartbeat",
    labelnames=("service_id", "environment"),
)
kafka_consumer_lag = Gauge(
    "plantrace_kafka_consumer_lag",
    "Kafka consumer lag estimate",
    labelnames=("topic",),
)
api_request_latency_seconds = Histogram(
    "plantrace_api_request_latency_seconds",
    "HTTP request latency",
    labelnames=("path", "method", "status"),
)
diagnostic_latency_seconds = Histogram(
    "plantrace_diagnostic_latency_seconds",
    "Latency of query diagnostic evaluation",
    labelnames=("source",),
)
placement_latency_seconds = Histogram(
    "plantrace_placement_latency_seconds",
    "Latency of placement simulation execution",
    labelnames=("algorithm",),
)
