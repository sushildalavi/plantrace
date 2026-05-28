# QueryLens v2 Architecture

## Data plane

PostgreSQL (`pg_stat_statements`, `pgvector`) -> C++ collector (`libpqxx`, protobuf) -> Kafka/Redpanda topics (`query-telemetry`, `collector-heartbeats`, `telemetry-dlq`).

## Control plane

FastAPI service:
- consumes telemetry with `aiokafka`
- persists snapshots and regressions
- applies deterministic rule engine
- handles retries/backoff
- routes failed events to DLQ
- exposes `/health`, `/metrics`, and API endpoints

## Persistence

`querylens` schema includes:
- `query_fingerprints`
- `query_metrics` (`event_id`, `ingested_at`)
- `query_plans`
- `query_regressions`
- `query_reports`
- `collector_status`
- `dlq_events`

## Ops plane

Prometheus scrapes backend `/metrics`, loads alert rules, and Grafana dashboards are provisioned from repository files.
