from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.evidence import EvidenceBundle  # noqa: E402
from app.ai.heuristics import build_heuristic_report  # noqa: E402
from app.ai.providers import FakeProvider, build_ollama_candidates  # noqa: E402
from app.ai.service import QueryRegressionInvestigator  # noqa: E402
from app.schemas import DiagnosticOut, FingerprintOut, MetricPoint, PlanSummary, RegressionOut  # noqa: E402


def _hash(sql: str) -> str:
    return hashlib.sha256(sql.lower().encode("utf-8")).hexdigest()


def _metric(captured_at: datetime, mean: float, calls: int, rows: int, temp: int) -> MetricPoint:
    return MetricPoint(
        captured_at=captured_at,
        calls=calls,
        total_exec_time_ms=mean * calls,
        mean_exec_time_ms=mean,
        rows_returned=rows,
        shared_blks_hit=100,
        shared_blks_read=20,
        temp_blks_written=temp,
    )


def _plan(
    captured_at: datetime,
    *,
    seq: bool,
    idx: bool,
    actual: int,
    estimated: int,
    node: str,
) -> PlanSummary:
    return PlanSummary(
        id=uuid4(),
        captured_at=captured_at,
        top_node_type=node,
        uses_seq_scan=seq,
        uses_index_scan=idx,
        estimated_total_cost=500.0 if seq else 80.0,
        actual_rows=actual,
        estimated_rows=estimated,
    )


def _fingerprint(sql: str, captured_at: datetime) -> FingerprintOut:
    return FingerprintOut(
        id=uuid4(),
        fingerprint_hash=_hash(sql),
        normalized_query=sql.lower(),
        first_seen_at=captured_at - timedelta(hours=1),
        last_seen_at=captured_at,
    )


def build_case_bundle(case: str) -> EvidenceBundle:
    now = datetime.now(UTC)
    if case == "thin":
        fp = _fingerprint("SELECT 1", now)
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[],
            latest_plan=None,
            previous_plan=None,
            diagnostics=[],
            regressions=[],
        )

    if case == "row_estimate":
        fp = _fingerprint("SELECT * FROM orders WHERE user_id = $1", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=2200, estimated=140, node="Seq Scan")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=220, estimated=180, node="Index Scan")
        diagnostics = [
            DiagnosticOut(
                id=uuid4(),
                fingerprint_id=fp.id,
                plan_id=latest_plan.id,
                diagnostic_type="row_estimate_mismatch",
                severity="medium",
                title="Row estimate diverges from reality",
                explanation="Planner estimates are far below observed rows.",
                suggested_action="Refresh statistics and inspect predicates.",
                evidence_json={"ratio": 15.7},
                created_at=now,
            )
        ]
        regressions = [
            RegressionOut(
                id=uuid4(),
                fingerprint_id=fp.id,
                severity="high",
                regression_type="latency_spike",
                message="Mean latency jumped after the last capture.",
                old_metric_json={"mean_exec_time_ms": 1.2},
                new_metric_json={"mean_exec_time_ms": 7.2},
                created_at=now,
            )
        ]
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 1.2, 100, 250, 0),
                _metric(now - timedelta(minutes=10), 2.0, 120, 275, 5),
                _metric(now, 7.2, 140, 300, 25),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=diagnostics,
            regressions=regressions,
        )

    if case == "placement":
        fp = _fingerprint("SELECT * FROM tenant_usage WHERE tenant_id = $1", now)
        metrics = [
            _metric(now - timedelta(minutes=20), 1.0, 100, 200, 0),
            _metric(now - timedelta(minutes=10), 1.8, 120, 240, 2),
            _metric(now, 5.8, 150, 280, 18),
        ]
        latest_plan = _plan(now, seq=True, idx=False, actual=1800, estimated=140, node="Seq Scan")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=220, estimated=180, node="Index Scan")
        diagnostics = [
            DiagnosticOut(
                id=uuid4(),
                fingerprint_id=fp.id,
                plan_id=latest_plan.id,
                diagnostic_type="row_estimate_mismatch",
                severity="medium",
                title="Row estimate diverges from reality",
                explanation="Planner estimates are far lower than observed rows.",
                suggested_action="Refresh statistics and inspect predicates.",
                evidence_json={"ratio": 12.8},
                created_at=now,
            )
        ]
        regressions = [
            RegressionOut(
                id=uuid4(),
                fingerprint_id=fp.id,
                severity="high",
                regression_type="latency_spike",
                message="Latency jumped after the last capture.",
                old_metric_json={"mean_exec_time_ms": 1.0},
                new_metric_json={"mean_exec_time_ms": 5.8},
                created_at=now,
            )
        ]
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=metrics,
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=diagnostics,
            regressions=regressions,
        )

    if case == "temp_spill":
        fp = _fingerprint("SELECT tenant_id, count(*) FROM events GROUP BY tenant_id ORDER BY count(*) DESC", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=3400, estimated=220, node="HashAggregate")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=340, estimated=210, node="Index Scan")
        diagnostics = [
            DiagnosticOut(
                id=uuid4(),
                fingerprint_id=fp.id,
                plan_id=latest_plan.id,
                diagnostic_type="temp_sort_hash_spill",
                severity="high",
                title="Hash aggregate spilled to temp",
                explanation="Temp write volume rose sharply on the latest run.",
                suggested_action="Increase work_mem or reduce fanout.",
                evidence_json={"temp_blks_written": 25, "spill_ratio": 3.4},
                created_at=now,
            )
        ]
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 2.2, 80, 220, 1),
                _metric(now - timedelta(minutes=10), 5.4, 95, 235, 8),
                _metric(now, 14.6, 110, 260, 42),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=diagnostics,
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="high",
                    regression_type="temp_spill",
                    message="Temp spill appeared in the latest capture.",
                    old_metric_json={"temp_blks_written": 8},
                    new_metric_json={"temp_blks_written": 42},
                    created_at=now,
                )
            ],
        )

    if case == "nested_loop":
        fp = _fingerprint("SELECT * FROM users u JOIN orders o ON o.user_id = u.id WHERE u.region = $1", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=18000, estimated=280, node="Nested Loop")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=1600, estimated=220, node="Hash Join")
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 3.1, 60, 180, 0),
                _metric(now - timedelta(minutes=10), 9.5, 64, 190, 2),
                _metric(now, 22.8, 72, 210, 10),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=[
                DiagnosticOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    plan_id=latest_plan.id,
                    diagnostic_type="nested_loop_explosion",
                    severity="critical",
                    title="Nested loop expansion detected",
                    explanation="Join cardinality exploded after the latest capture.",
                    suggested_action="Add join support or rewrite the predicate.",
                    evidence_json={"join_rows": 18000, "estimate_rows": 280},
                    created_at=now,
                )
            ],
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="critical",
                    regression_type="nested_loop_explosion",
                    message="Nested loop introduced a severe latency spike.",
                    old_metric_json={"mean_exec_time_ms": 3.1},
                    new_metric_json={"mean_exec_time_ms": 22.8},
                    created_at=now,
                )
            ],
        )

    if case == "vector_bypass":
        fp = _fingerprint("SELECT * FROM vector_items ORDER BY embedding <-> $1 LIMIT 20", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=2200, estimated=90, node="Seq Scan")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=140, estimated=80, node="Index Scan using vector_items_embedding_hnsw_idx")
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 1.4, 90, 160, 0),
                _metric(now - timedelta(minutes=10), 2.8, 100, 175, 1),
                _metric(now, 8.9, 110, 190, 3),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=[
                DiagnosticOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    plan_id=latest_plan.id,
                    diagnostic_type="vector_hnsw_bypass",
                    severity="high",
                    title="Vector index bypassed",
                    explanation="The latest plan reverted to a sequential scan over the vector table.",
                    suggested_action="Check operator support and index usage.",
                    evidence_json={"expected_index": "hnsw", "actual_node": "Seq Scan"},
                    created_at=now,
                )
            ],
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="high",
                    regression_type="vector_hnsw_bypass",
                    message="Vector query stopped using the HNSW path.",
                    old_metric_json={"mean_exec_time_ms": 1.4},
                    new_metric_json={"mean_exec_time_ms": 8.9},
                    created_at=now,
                )
            ],
        )

    if case == "index_to_seq":
        fp = _fingerprint("SELECT * FROM orders WHERE created_at >= now() - interval '1 day'", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=4400, estimated=300, node="Seq Scan")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=520, estimated=260, node="Index Scan")
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 1.0, 70, 150, 0),
                _metric(now - timedelta(minutes=10), 2.1, 80, 160, 1),
                _metric(now, 6.8, 90, 170, 4),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=[
                DiagnosticOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    plan_id=latest_plan.id,
                    diagnostic_type="seq_scan_fallback",
                    severity="medium",
                    title="Index scan fell back to sequential scan",
                    explanation="The latest capture no longer uses the available index path.",
                    suggested_action="Check predicates, statistics, and index selectivity.",
                    evidence_json={"previous_node": "Index Scan", "current_node": "Seq Scan"},
                    created_at=now,
                )
            ],
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="high",
                    regression_type="index_to_seq",
                    message="A selective index path regressed to sequential scan.",
                    old_metric_json={"mean_exec_time_ms": 1.0},
                    new_metric_json={"mean_exec_time_ms": 6.8},
                    created_at=now,
                )
            ],
        )

    if case == "call_spike":
        fp = _fingerprint("SELECT tenant_id, count(*) FROM audit_events WHERE tenant_id = $1", now)
        latest_plan = _plan(now, seq=False, idx=True, actual=340, estimated=300, node="Index Scan")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=320, estimated=280, node="Index Scan")
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 0.9, 120, 140, 0),
                _metric(now - timedelta(minutes=10), 1.1, 240, 180, 0),
                _metric(now, 1.5, 960, 220, 1),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=[
                DiagnosticOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    plan_id=latest_plan.id,
                    diagnostic_type="call_spike",
                    severity="medium",
                    title="Call volume spiked sharply",
                    explanation="The query is being invoked far more frequently than prior snapshots.",
                    suggested_action="Investigate upstream fanout or batching.",
                    evidence_json={"calls": 960, "previous_calls": 240},
                    created_at=now,
                )
            ],
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="medium",
                    regression_type="call_spike",
                    message="Call count jumped sharply.",
                    old_metric_json={"calls": 240},
                    new_metric_json={"calls": 960},
                    created_at=now,
                )
            ],
        )

    if case == "cost_spike":
        fp = _fingerprint("SELECT * FROM orders WHERE status = $1 ORDER BY created_at DESC", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=3800, estimated=260, node="Sort")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=180, estimated=220, node="Index Scan")
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 1.6, 80, 120, 0),
                _metric(now - timedelta(minutes=10), 3.7, 90, 150, 4),
                _metric(now, 11.2, 110, 170, 16),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=[
                DiagnosticOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    plan_id=latest_plan.id,
                    diagnostic_type="cost_spike",
                    severity="medium",
                    title="Estimated cost jumped",
                    explanation="The plan cost rose with a scan and sort-heavy shape.",
                    suggested_action="Check sort order and predicate support.",
                    evidence_json={"estimated_total_cost": 500.0},
                    created_at=now,
                )
            ],
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="high",
                    regression_type="cost_spike",
                    message="Estimated cost spiked on the latest capture.",
                    old_metric_json={"estimated_total_cost": 80.0},
                    new_metric_json={"estimated_total_cost": 500.0},
                    created_at=now,
                )
            ],
        )

    if case == "missing_index_candidate":
        fp = _fingerprint("SELECT * FROM invoices WHERE customer_id = $1 AND status = 'open'", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=2600, estimated=180, node="Seq Scan")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=180, estimated=160, node="Index Scan")
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 1.4, 90, 140, 0),
                _metric(now - timedelta(minutes=10), 2.9, 100, 160, 1),
                _metric(now, 8.4, 120, 180, 9),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=[
                DiagnosticOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    plan_id=latest_plan.id,
                    diagnostic_type="missing_index_candidate",
                    severity="medium",
                    title="Potential index candidate missing",
                    explanation="The filter is selective, but the latest plan falls back to a sequential scan.",
                    suggested_action="Evaluate a customer_id/status index.",
                    evidence_json={"filter_columns": ["customer_id", "status"]},
                    created_at=now,
                )
            ],
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="high",
                    regression_type="missing_index_candidate",
                    message="A selective lookup lost its likely index path.",
                    old_metric_json={"mean_exec_time_ms": 1.4},
                    new_metric_json={"mean_exec_time_ms": 8.4},
                    created_at=now,
                )
            ],
        )

    if case == "bad_vector_operator":
        fp = _fingerprint("SELECT * FROM chunks ORDER BY embedding <=> $1 LIMIT 10", now)
        latest_plan = _plan(now, seq=True, idx=False, actual=1200, estimated=70, node="Seq Scan")
        previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=90, estimated=80, node="Index Scan using chunks_embedding_hnsw_idx")
        return EvidenceBundle(
            fingerprint=fp,
            metric_window=[
                _metric(now - timedelta(minutes=20), 1.1, 80, 110, 0),
                _metric(now - timedelta(minutes=10), 2.0, 85, 120, 0),
                _metric(now, 6.2, 95, 130, 2),
            ],
            latest_plan=latest_plan,
            previous_plan=previous_plan,
            diagnostics=[
                DiagnosticOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    plan_id=latest_plan.id,
                    diagnostic_type="vector_operator_mismatch",
                    severity="high",
                    title="Vector operator and index path mismatch",
                    explanation="The query uses a distance operator that no longer matches the index strategy.",
                    suggested_action="Align the operator class with the ANN index definition.",
                    evidence_json={"operator": "<=>", "index": "hnsw"},
                    created_at=now,
                )
            ],
            regressions=[
                RegressionOut(
                    id=uuid4(),
                    fingerprint_id=fp.id,
                    severity="high",
                    regression_type="vector_operator_mismatch",
                    message="Vector operator no longer matches the ANN index path.",
                    old_metric_json={"mean_exec_time_ms": 1.1},
                    new_metric_json={"mean_exec_time_ms": 6.2},
                    created_at=now,
                )
            ],
        )

    fp = _fingerprint("SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC", now)
    metrics = [
        _metric(now - timedelta(minutes=20), 1.2, 100, 250, 0),
        _metric(now - timedelta(minutes=10), 2.0, 120, 275, 5),
        _metric(now, 7.2, 140, 300, 25),
    ]
    latest_plan = _plan(now, seq=True, idx=False, actual=2200, estimated=140, node="Seq Scan")
    previous_plan = _plan(now - timedelta(minutes=10), seq=False, idx=True, actual=220, estimated=180, node="Index Scan")
    diagnostics = [
        DiagnosticOut(
            id=uuid4(),
            fingerprint_id=fp.id,
            plan_id=latest_plan.id,
            diagnostic_type="row_estimate_mismatch",
            severity="medium",
            title="Row estimate diverges from reality",
            explanation="Planner estimates are far lower than observed rows.",
            suggested_action="Refresh statistics and inspect predicates.",
            evidence_json={"ratio": 15.7},
            created_at=now,
        )
    ]
    regressions = [
        RegressionOut(
            id=uuid4(),
            fingerprint_id=fp.id,
            severity="high",
            regression_type="latency_spike",
            message="Mean latency jumped after the last capture.",
            old_metric_json={"mean_exec_time_ms": 1.2},
            new_metric_json={"mean_exec_time_ms": 7.2},
            created_at=now,
        )
    ]
    return EvidenceBundle(
        fingerprint=fp,
        metric_window=metrics,
        latest_plan=latest_plan,
        previous_plan=previous_plan,
        diagnostics=diagnostics,
        regressions=regressions,
    )


@dataclass
class EvaluationRow:
    case: str
    schema_valid: bool
    evidence_coverage: float
    unsupported_claims: int
    recommendation_relevant: bool
    insufficient_expected: bool
    insufficient_observed: bool
    latency_ms: float


def run_suite(provider: str) -> dict[str, object]:
    cases = [
        "thin",
        "placement",
        "latency",
        "row_estimate",
        "temp_spill",
        "nested_loop",
        "vector_bypass",
        "index_to_seq",
        "call_spike",
        "cost_spike",
        "missing_index_candidate",
        "bad_vector_operator",
    ]

    if provider == "fake":
        def service_factory(bundle: EvidenceBundle) -> QueryRegressionInvestigator:
            return QueryRegressionInvestigator(
                providers=[FakeProvider(response=build_heuristic_report(bundle).model_dump_json())],
                timeout_seconds=2,
            )

    elif provider == "ollama":
        candidates = build_ollama_candidates(
            model_name="qwen2.5-coder:7b",
            fallback_model="llama3.1:8b",
            base_url="http://localhost:11434",
        )

        def service_factory(_: EvidenceBundle) -> QueryRegressionInvestigator:
            return QueryRegressionInvestigator(providers=candidates, timeout_seconds=20)
    else:
        raise ValueError(provider)

    rows: list[EvaluationRow] = []
    for case in cases:
        bundle = build_case_bundle(case)
        service = service_factory(bundle)
        response = service.investigate_bundle(bundle=bundle)
        schema_valid = response.__class__.model_validate(response.model_dump()) is not None
        matched = sum(1 for item in response.report.evidence if item.signal in bundle.signal_inventory)
        coverage = matched / max(len(response.report.evidence), 1)
        rows.append(
            EvaluationRow(
                case=case,
                schema_valid=schema_valid,
                evidence_coverage=coverage,
                unsupported_claims=len(response.report.unsupported_claims),
                recommendation_relevant=bool(
                    response.report.index_recommendation or response.report.query_rewrite_suggestion or response.report.suggested_actions
                ),
                insufficient_expected=bundle.is_thin,
                insufficient_observed=response.report.insufficient_evidence,
                latency_ms=response.latency_ms,
            )
        )

    return {
        "provider": provider,
        "golden_cases_tested": len(rows),
        "schema_validity_rate": round(sum(1 for row in rows if row.schema_valid) / len(rows), 3),
        "evidence_coverage_rate": round(sum(row.evidence_coverage for row in rows) / len(rows), 3),
        "unsupported_claim_rate": round(sum(1 for row in rows if row.unsupported_claims > 0) / len(rows), 3),
        "recommendation_relevance_rate": round(
            sum(1 for row in rows if row.recommendation_relevant) / len(rows), 3
        ),
        "insufficient_evidence_behavior": round(
            sum(1 for row in rows if row.insufficient_expected == row.insufficient_observed) / len(rows), 3
        ),
        "average_report_generation_latency_ms": round(sum(row.latency_ms for row in rows) / len(rows), 2),
        "cases": [row.__dict__ for row in rows],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Query Regression Investigator.")
    parser.add_argument(
        "--provider",
        choices=["fake", "ollama"],
        default="fake",
        help="Use the fake provider by default; choose ollama for an optional local smoke.",
    )
    args = parser.parse_args()

    if args.provider == "ollama":
        try:
            output = run_suite("ollama")
        except Exception as exc:
            print(json.dumps({"provider": "ollama", "skipped": True, "reason": str(exc)}, indent=2))
            return 0
    else:
        output = run_suite("fake")

    out_dir = ROOT / "backend" / "benchmark_results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "query_investigator_eval.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    with (out_dir / "query_investigator_eval.csv").open("w", encoding="utf-8", newline="") as f:
        import csv

        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case",
                "schema_valid",
                "evidence_coverage",
                "unsupported_claims",
                "recommendation_relevant",
                "insufficient_expected",
                "insufficient_observed",
                "latency_ms",
            ],
        )
        writer.writeheader()
        for case in output["cases"]:
            writer.writerow(case)

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
