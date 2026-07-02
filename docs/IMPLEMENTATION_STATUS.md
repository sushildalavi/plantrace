# Implementation Status

This table separates what PlanTrace actually implements from the Azure Data-style positioning used in the UI and README.

| Capability | Status | Evidence | Notes |
|---|---|---|---|
| PostgreSQL telemetry ingestion | Implemented | Collector, Kafka/Redpanda topics, backend consumer, `pg_stat_statements` | Real local ingestion path. |
| Query fingerprinting | Implemented | `backend/app/core/fingerprint.py`, query summaries | Normalizes SQL before hashing. |
| EXPLAIN / EXPLAIN ANALYZE parsing | Implemented | Plan parsing helpers, plan viewer, diagnostics | Local PostgreSQL plans only. |
| Regression detection | Implemented | Deterministic regression rules and evaluation artifacts | Eight regression classes are present in the repo. |
| Diagnostic generation | Implemented | Six diagnostic classes in `backend/app/core/diagnostics.py` | Evidence-backed and rule-based. |
| Query Regression Investigator / AI SQL Copilot | Implemented | `scripts/evaluate_query_investigator.py`, API route, fake provider tests | Evidence-grounded, schema-validated, and now includes root cause, rewrite, and index guidance. |
| Placement optimization simulation | Implemented as synthetic what-if | `backend/app/core/placement.py`, placement eval script | No real cluster control; includes first-fit, best-fit, weighted scoring, local search, and simulated annealing. |
| Azure deployment / Azure SQLDB integration | Not implemented | No Azure cloud resources, no Azure SDK deployment path | Use "Azure Data-style" positioning only. |
| Production observability dashboards | Partially implemented | React dashboard, Prometheus, Grafana provisioning | Local demo stack only. |
| Large-scale benchmark proof | Partially implemented | Checked-in 10K/50K/100K artifacts, benchmark runner presets, and canonical summary script | Benchmarks are synthetic local telemetry runs; 250K/500K/1M presets are supported as pending or live modes. |
