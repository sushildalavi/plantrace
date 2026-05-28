# Benchmarks

QueryLens includes a reproducible ingestion benchmark script:

- `scripts/benchmark_ingestion.py`

It publishes synthetic valid `QueryTelemetryEvent` protobuf messages to Kafka and measures real local ingestion outcomes.
Each run now:
- acquires a DB advisory lock so only one benchmark executes at a time
- clears prior `select benchmark_%` rows before publishing
- records metric deltas from a pre-run baseline
- uses a unique `run_id` with microseconds + random suffix

## Run

```bash
make benchmark N=10000
make benchmark N=50000
make benchmark-100k
```

## Outputs

- `benchmark_results/querylens_benchmark_<N>.json`
- `benchmark_results/querylens_benchmark_<N>.csv`

Fields include:
- total events
- events/sec
- ingest latency p50/p95/p99 (from `captured_at` to persisted `ingested_at`)
- Kafka lag peak and lag recovery time
- duplicate events skipped
- DLQ events
- persistence failures
- consumed row count and whether it matches requested event count

These are local-machine measurements and should not be compared across hardware blindly.
