# PlanTrace Benchmark Summary

Synthetic local telemetry benchmarks generated from `backend/benchmark_results`.

## Environment

- stack: local docker compose stack
- database: pgvector/pgvector:pg16
- broker: redpandadata/redpanda:v25.1.2
- backend: FastAPI control plane
- collector: telemetry benchmark + on-demand collector

## Telemetry Benchmarks

| Artifact | Events | Consumed | Completion | Throughput | p50 ms | p95 ms | p99 ms | DLQ | Persistence failures | Duplicate skips | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| plantrace_benchmark_250000.json | 250,000 | — | — | — | — | — | — | — | — | — | pending |
| plantrace_benchmark_500000.json | 500,000 | — | — | — | — | — | — | — | — | — | pending |
| querylens_benchmark_10000.json | 10,000 | 10,000 | — | 7,998.27 | 16,406.91 | 31,586.53 | 33,127.21 | 0.00 | 0.00 | 0.00 | measured |
| querylens_benchmark_100000.json | 100,000 | 100,000 | — | 8,938.52 | 165,254.86 | 327,040.64 | 340,567.16 | 0.00 | 0.00 | 0.00 | measured |
| querylens_benchmark_50000.json | 50,000 | 50,000 | — | 9,067.61 | 82,649.36 | 160,425.76 | 167,557.34 | 0.00 | 0.00 | 0.00 | measured |

## Benchmark Takeaways

- measured artifacts: 3
- best throughput: 9067.61 events/sec (querylens_benchmark_50000.json)
- largest run: 100000 events (querylens_benchmark_100000.json)
- artifacts with zero DLQ: 3
- artifacts with zero persistence failures: 3

## Regression Evaluation

- scenarios: 9
- true positives: 8
- false positives: 0
- false negatives: 0
- precision: 1.0
- recall: 1.0
- f1: 1.0

## Investigator Evaluation

- golden cases tested: 12
- schema validity: 1.0
- evidence coverage: 1.0
- insufficient-evidence behavior: 1.0
- average latency ms: 41.6

## Placement Evaluation

- scenarios: 4
- algorithms: 5
- best balance improvement: 0.243213
- best hotspot reduction: 0.084007
- max overloaded-node reduction: 0.25
