# PlanTrace Architecture

## Data plane

PostgreSQL (`pg_stat_statements`, `pgvector`) -> C++ collector (`libpqxx`, protobuf) -> Kafka/Redpanda topics (`query-telemetry`, `collector-heartbeats`, `telemetry-dlq`).

## Control plane

FastAPI service:
- consumes telemetry with `aiokafka`
- persists snapshots and regressions
- stores diagnostic findings derived from EXPLAIN ANALYZE evidence
- applies deterministic rule engine
- handles retries/backoff
- routes failed events to DLQ
- exposes `/health`, `/metrics`, and API endpoints

## Presentation plane

React serves two surfaces:
- a public landing page at `/` that explains the product story and demo mode
- an app workspace at `/app` with dedicated routes for queries, regressions, placement simulation, saved reports, and the Query Regression Investigator

The app shell keeps the demo mode banner explicit and routes reviewers through `/learn` for architecture context.

## Simulator plane

The placement simulator uses synthetic tenant telemetry to compare first-fit, greedy best-fit, weighted scoring, and local-search rebalance strategies. It is a what-if model for database placement planning, not a live control plane for production clusters.

## Investigation plane

The Query Regression Investigator reads query fingerprints, metric history, regression records, and diagnostics, then compacts the evidence into a structured report. The workflow uses LangChain for provider abstraction and structured output, LangGraph for the evidence-collection and validation steps, and Ollama only when explicitly enabled.

- Default provider mode is disabled so normal startup does not require a local model server
- CI uses a fake provider to exercise the full request/validation path without external dependencies
- The investigator is evidence-grounded and falls back to an `insufficient_evidence` report when telemetry is too thin or model output cannot be grounded
- Placement references remain synthetic what-if context only; the investigator never claims live cluster control

## Persistence

`querylens` schema includes:
- `query_fingerprints`
- `query_metrics` (`event_id`, `ingested_at`)
- `query_plans`
- `query_regressions`
- `query_reports`
- `collector_status`
- `dlq_events`

The internal schema and metric prefixes stay on `querylens` for backwards compatibility with the existing Docker, migration, and dashboard wiring.

## Ops plane

Prometheus scrapes backend `/metrics`, loads alert rules, and Grafana dashboards are provisioned from repository files.
