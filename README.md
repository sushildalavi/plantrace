# QueryLens v2 — PostgreSQL Observability Platform

QueryLens v2 is a production-style local platform for PostgreSQL query observability.

## What is implemented

- C++ telemetry collector (`libpqxx`) with SQL normalization, SHA-256 fingerprinting, vector operator detection (`<=>`, `<->`, `<#>`), and safe-gated `EXPLAIN (FORMAT JSON)`.
- Protobuf telemetry contracts.
- Kafka streaming pipeline (Redpanda-compatible broker in Docker Compose).
- FastAPI control plane with aiokafka consumer, deterministic regression detection, REST APIs, and Prometheus metrics.
- PostgreSQL persistence in `querylens` schema.
- React dashboard (existing v1 views preserved and extended for critical severity + collector status hints).
- Prometheus + Grafana observability stack.

## Architecture

PostgreSQL (`pg_stat_statements`, `pgvector`) -> C++ collector -> Kafka (`query-telemetry`) -> FastAPI consumer -> `querylens` schema -> React UI.

Detailed docs:

- `docs/ARCHITECTURE.md`
- `docs/REGRESSION_RULES.md`
- `docs/DEMO.md`
- `docs/OPERATIONS.md`

## Services / Ports

- Frontend: `http://localhost:3030`
- Backend API: `http://localhost:8765`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (`admin/admin`)
- Postgres: `localhost:5434`
- Kafka broker: `localhost:9092`

## Quickstart

```bash
make build
make up
make migrate
make seed
make demo
```

## Make Commands

- `make setup`
- `make build`
- `make up`
- `make down`
- `make logs`
- `make migrate`
- `make seed`
- `make workload`
- `make collect`
- `make collect-cpp`
- `make demo`
- `make test`
- `make test-backend`
- `make test-collector`
- `make test-frontend`
- `make lint`
- `make clean`

## Regression Rules (deterministic)

- severe latency spike (high): ratio >= 5x baseline
- latency spike (medium): ratio >= 2x baseline
- index->seq fallback (high)
- vector HNSW bypass (critical)
- row-estimate mismatch (medium): actual/estimated >= 10x
- temp spill (medium)
- call spike (low)
- cost spike (medium)

Thresholds are configurable in `backend/app/config.py`.

## Limitations

- Collector currently publishes `QueryTelemetryEvent` on `query-telemetry`; heartbeat publishing can be added similarly.
- Consumer lag metric is best-effort based on topic/partition position and end offsets.
- No Kubernetes deployment in this repository.

## Resume bullets (only for implemented features)

- Built a C++ (`libpqxx`) PostgreSQL telemetry collector that fingerprints normalized SQL, safely captures `EXPLAIN JSON`, and streams protobuf events to Kafka.
- Implemented a FastAPI control plane with aiokafka ingestion, deterministic regression detection (including pgvector HNSW bypass), and historical persistence in PostgreSQL.
- Added platform observability with Prometheus metrics and Grafana provisioning, plus reproducible Docker Compose demo workflows for relational and vector regression scenarios.
