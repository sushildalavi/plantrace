from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "backend" / "benchmark_results"
DOC = ROOT / "docs" / "BENCHMARK_SUMMARY.md"
JSON_OUT = RESULTS / "canonical_benchmark_summary.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_num(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return f"{value:,}" if isinstance(value, int) else str(value)


def _artifact_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted({*RESULTS.glob("plantrace_benchmark_*.json"), *RESULTS.glob("querylens_benchmark_*.json")}):
        payload = _load_json(path)
        events = payload.get("submitted_events", payload.get("events"))
        if isinstance(events, int) and events < 10_000:
            continue
        rows.append(
            {
                "artifact": path.name,
                "events": events,
                "consumed": payload.get("consumed_events", payload.get("consumed_count")),
                "throughput": payload.get("collector_throughput_events_per_sec") or payload.get("events_per_second"),
                "p50": payload.get("p50_ingestion_latency_ms") or payload.get("ingest_latency_ms_p50"),
                "p95": payload.get("p95_ingestion_latency_ms") or payload.get("ingest_latency_ms_p95"),
                "p99": payload.get("p99_ingestion_latency_ms") or payload.get("ingest_latency_ms_p99"),
                "completion": payload.get("event_completion_rate"),
                "dlq": payload.get("dlq_count") or payload.get("dlq_events_delta"),
                "persistence_failures": payload.get("persistence_failures") or payload.get("persistence_failures_delta"),
                "duplicate_events_skipped": payload.get("duplicate_events_skipped") or payload.get("duplicate_events_skipped_delta"),
                "status": payload.get("status", "measured"),
                "preset": payload.get("preset", "standard"),
                "environment": payload.get("environment", {}),
            }
        )
    return rows


def _summary_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [row for row in rows if row["status"] == "measured"]
    if not measured:
        return {"measured_count": 0}

    best = max(measured, key=lambda row: row["throughput"] or 0)
    max_event = max(measured, key=lambda row: row["events"] or 0)
    zero_dlq = sum(1 for row in measured if not row["dlq"])
    zero_fail = sum(1 for row in measured if not row["persistence_failures"])
    return {
        "measured_count": len(measured),
        "best_throughput": best["throughput"],
        "best_throughput_artifact": best["artifact"],
        "max_events": max_event["events"],
        "max_events_artifact": max_event["artifact"],
        "zero_dlq_artifacts": zero_dlq,
        "zero_failure_artifacts": zero_fail,
    }


def _read_eval(name: str) -> dict[str, Any] | None:
    path = RESULTS / name
    if not path.exists():
        return None
    return _load_json(path)


def build_summary() -> dict[str, Any]:
    benchmark_rows = _artifact_rows()
    regression = _read_eval("regression_eval.json")
    placement = _read_eval("placement_eval.json")
    investigator = _read_eval("query_investigator_eval.json")

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_dir": str(RESULTS),
        "environment": {
            "database": "pgvector/pgvector:pg16",
            "broker": "redpandadata/redpanda:v25.1.2",
            "backend": "FastAPI control plane",
            "collector": "telemetry benchmark + on-demand collector",
            "stack": "local docker compose stack",
        },
        "benchmarks": benchmark_rows,
        "benchmark_summary": _summary_rows(benchmark_rows),
        "regression_eval": regression,
        "placement_eval": placement,
        "investigator_eval": investigator,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# PlanTrace Benchmark Summary",
        "",
        "Synthetic local telemetry benchmarks generated from `backend/benchmark_results`.",
        "",
        "## Environment",
        "",
        f"- stack: {summary['environment']['stack']}",
        f"- database: {summary['environment']['database']}",
        f"- broker: {summary['environment']['broker']}",
        f"- backend: {summary['environment']['backend']}",
        f"- collector: {summary['environment']['collector']}",
        "",
        "## Telemetry Benchmarks",
        "",
        "| Artifact | Events | Consumed | Completion | Throughput | p50 ms | p95 ms | p99 ms | DLQ | Persistence failures | Duplicate skips | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary["benchmarks"]:
        lines.append(
            "| {artifact} | {events} | {consumed} | {completion} | {throughput} | {p50} | {p95} | {p99} | {dlq} | {persistence_failures} | {duplicate_events_skipped} | {status} |".format(
                artifact=row["artifact"],
                events=_format_num(row["events"]),
                consumed=_format_num(row["consumed"]),
                completion=_format_num(row["completion"]),
                throughput=_format_num(row["throughput"]),
                p50=_format_num(row["p50"]),
                p95=_format_num(row["p95"]),
                p99=_format_num(row["p99"]),
                dlq=_format_num(row["dlq"]),
                persistence_failures=_format_num(row["persistence_failures"]),
                duplicate_events_skipped=_format_num(row["duplicate_events_skipped"]),
                status=row["status"],
            )
        )

    bench_summary = summary["benchmark_summary"]
    lines.extend(
        [
            "",
            "## Benchmark Takeaways",
            "",
            f"- measured artifacts: {bench_summary.get('measured_count', 0)}",
            f"- best throughput: {bench_summary.get('best_throughput')} events/sec ({bench_summary.get('best_throughput_artifact')})",
            f"- largest run: {bench_summary.get('max_events')} events ({bench_summary.get('max_events_artifact')})",
            f"- artifacts with zero DLQ: {bench_summary.get('zero_dlq_artifacts')}",
            f"- artifacts with zero persistence failures: {bench_summary.get('zero_failure_artifacts')}",
        ]
    )

    if summary.get("regression_eval"):
        r = summary["regression_eval"]
        lines.extend(
            [
                "",
                "## Regression Evaluation",
                "",
                f"- scenarios: {r.get('scenarios')}",
                f"- true positives: {r.get('tp')}",
                f"- false positives: {r.get('fp')}",
                f"- false negatives: {r.get('fn')}",
                f"- precision: {r.get('precision')}",
                f"- recall: {r.get('recall')}",
                f"- f1: {r.get('f1')}",
            ]
        )

    if summary.get("investigator_eval"):
        i = summary["investigator_eval"]
        lines.extend(
            [
                "",
                "## Investigator Evaluation",
                "",
                f"- golden cases tested: {i.get('golden_cases_tested')}",
                f"- schema validity: {i.get('schema_validity_rate')}",
                f"- evidence coverage: {i.get('evidence_coverage_rate')}",
                f"- insufficient-evidence behavior: {i.get('insufficient_evidence_behavior')}",
                f"- average latency ms: {i.get('average_report_generation_latency_ms')}",
            ]
        )

    if summary.get("placement_eval"):
        p = summary["placement_eval"]
        lines.extend(
            [
                "",
                "## Placement Evaluation",
                "",
                f"- scenarios: {p.get('scenarios')}",
                f"- algorithms: {p.get('algorithms')}",
                f"- best balance improvement: {p.get('best_balance_improvement')}",
                f"- best hotspot reduction: {p.get('best_hotspot_reduction')}",
                f"- max overloaded-node reduction: {p.get('best_overloaded_reduction')}",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    JSON_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(render_markdown(summary), encoding="utf-8")
    print(JSON_OUT)
    print(DOC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
