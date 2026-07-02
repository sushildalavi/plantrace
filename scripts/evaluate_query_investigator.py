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

from app.ai.evidence import EvidenceBundle
from app.ai.heuristics import build_heuristic_report
from app.ai.providers import FakeProvider, build_ollama_candidates
from app.ai.service import QueryRegressionInvestigator
from app.schemas import DiagnosticOut, FingerprintOut, MetricPoint, PlanSummary, RegressionOut


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
    insufficient_expected: bool
    insufficient_observed: bool
    latency_ms: float


def run_suite(provider: str) -> dict[str, object]:
    cases = ["thin", "placement", "latency"]

    if provider == "fake":
        service_factory = lambda bundle: QueryRegressionInvestigator(
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

    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
