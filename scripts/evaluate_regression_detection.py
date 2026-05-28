from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.regression_detector import MetricSnapshot, PlanSnapshot, detect_regressions


def m(mean_ms=10.0, calls=100, temp=0):
    return MetricSnapshot(calls=calls, mean_ms=mean_ms, total_ms=mean_ms * max(calls, 1), rows=calls, temp_blks_written=temp)


def p(seq=False, idx=True, cost=10.0, actual=10, est=10, top="Index Scan"):
    return PlanSnapshot(
        uses_seq_scan=seq,
        uses_index_scan=idx,
        estimated_total_cost=cost,
        actual_rows=actual,
        estimated_rows=est,
        top_node_type=top,
    )


def evaluate():
    scenarios = [
        ("baseline_no_regression", None, m(10), m(10), p(False, True), p(False, True), False),
        ("index_to_seq", "index_scan_to_seq_scan", m(10), m(12), p(False, True), p(True, False, top="Seq Scan"), False),
        ("vector_hnsw_bypass", "vector_hnsw_index_bypass", m(10), m(12), p(False, True), p(True, False, top="Seq Scan"), True),
        ("severe_latency", "severe_latency_spike", m(10), m(55), p(), p(), False),
        ("latency_spike", "latency_spike", m(10), m(25), p(), p(), False),
        ("row_estimate", "row_estimate_mismatch", m(10), m(10), p(), p(actual=2000, est=50), False),
        ("temp_spill", "temp_spill", m(10, temp=100), m(10, temp=2200), p(), p(), False),
        ("cost_spike", "cost_spike", m(10), m(10), p(cost=100), p(cost=250), False),
        ("call_spike", "call_spike", m(10, calls=10), m(10, calls=30), p(), p(), False),
    ]

    rows = []
    tp = fp = fn = 0
    for name, expected, prev_m, new_m, prev_p, new_p, is_vec in scenarios:
        out = detect_regressions(prev_m, new_m, prev_p, new_p, is_vector_query=is_vec)
        detected = out[0]["regression_type"] if out else None

        if expected is None and detected is None:
            row_tp = row_fp = row_fn = 0
            outcome = "true_negative"
        elif expected == detected:
            tp += 1
            row_tp, row_fp, row_fn = 1, 0, 0
            outcome = "true_positive"
        elif expected is None and detected is not None:
            fp += 1
            row_tp, row_fp, row_fn = 0, 1, 0
            outcome = "false_positive"
        else:
            fn += 1
            row_tp, row_fp, row_fn = 0, 0, 1
            outcome = "false_negative"

        rows.append(
            {
                "scenario_name": name,
                "expected_regression_type": expected,
                "detected_regression_type": detected,
                "severity": out[0]["severity"] if out else None,
                "outcome": outcome,
                "tp": row_tp,
                "fp": row_fp,
                "fn": row_fn,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    summary = {
        "scenarios": len(scenarios),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "results": rows,
    }
    return summary


def main() -> None:
    summary = evaluate()
    out_dir = Path("benchmark_results")
    out_dir.mkdir(exist_ok=True)
    jpath = out_dir / "regression_eval.json"
    cpath = out_dir / "regression_eval.csv"
    jpath.write_text(json.dumps(summary, indent=2))

    with cpath.open("w", newline="") as f:
        fieldnames = ["scenario_name", "expected_regression_type", "detected_regression_type", "severity", "outcome", "tp", "fp", "fn"]
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in summary["results"]:
            w.writerow(r)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
