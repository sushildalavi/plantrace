# PlanTrace Benchmarks

## Status

- Benchmark artifacts exist and a canonical summary is generated in [docs/BENCHMARK_SUMMARY.md](BENCHMARK_SUMMARY.md).
- The benchmark runner now has a pending mode and live modes that reuse the telemetry benchmark when the local stack is up.
- Benchmark artifacts are generated locally from seeded scenarios; no production throughput claims are made here.

## Target metrics

- query events streamed
- event completion rate
- collector throughput events/sec
- p95 ingestion latency
- regression detection latency
- DLQ count/rate
- Kafka consumer lag
- regression classes detected
- diagnostic latency
- placement decision latency
- overloaded-node counts before/after synthetic placement

## Artifact names

- `backend/app/bench/telemetry_benchmark.py` writes `benchmark_results/plantrace_benchmark_*.json` and `.csv`
- `scripts/run_benchmark.py` supports `--preset standard|100k|250k|500k|1m` and reads those artifacts when live mode is available
- `scripts/generate_benchmark_summary.py` writes the canonical JSON and Markdown summary files
