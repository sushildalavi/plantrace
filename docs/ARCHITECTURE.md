# QueryLens v2 Architecture

QueryLens v2 uses a split data-plane/control-plane design.

- Data plane: PostgreSQL target + C++ collector + Kafka topics.
- Control plane: FastAPI + aiokafka consumer + deterministic regression engine + REST APIs.
- UI plane: React dashboard.
- Ops plane: Prometheus/Grafana.

## Topology

PostgreSQL (`pg_stat_statements`, `pgvector`) -> C++ collector (`libpqxx`, protobuf) -> Kafka (`query-telemetry`, `collector-heartbeats`) -> FastAPI consumer -> `querylens` schema -> React UI.

## Services / Ports

- frontend: `3030`
- backend: `8765` (container `8000`)
- postgres: `5434` (container `5432`)
- redpanda kafka: `9092`
- prometheus: `9090`
- grafana: `3000`

## Compatibility

Existing v1 endpoints are preserved:

- `/api/queries`
- `/api/regressions`
- `/api/collect/run`
- `/api/reports`

Added:

- `/api/collector/status`
- `/metrics`
