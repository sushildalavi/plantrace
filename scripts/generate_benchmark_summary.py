from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "backend" / "benchmark_results"
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
    for path in sorted(RESULTS.glob("plantrace_benchmark_*.json")):
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


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    JSON_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(JSON_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
