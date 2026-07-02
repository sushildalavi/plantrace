from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import QueryDiagnostic, QueryFingerprint, QueryMetric, QueryPlan, QueryRegression
from app.schemas import DiagnosticOut, FingerprintOut, MetricPoint, PlanSummary, RegressionOut


def _placement_relevant(normalized_query: str) -> bool:
    q = normalized_query.lower()
    return any(term in q for term in ("placement", "tenant", "cluster", "workload", "rebalance"))


@dataclass(slots=True)
class EvidenceBundle:
    fingerprint: FingerprintOut
    metric_window: list[MetricPoint]
    latest_plan: PlanSummary | None
    previous_plan: PlanSummary | None
    diagnostics: list[DiagnosticOut]
    regressions: list[RegressionOut]
    focus_regression: RegressionOut | None = None

    @property
    def latest_metric(self) -> MetricPoint | None:
        return self.metric_window[-1] if self.metric_window else None

    @property
    def evidence_count(self) -> int:
        total = len(self.metric_window) + len(self.diagnostics) + len(self.regressions)
        if self.latest_plan is not None:
            total += 1
        if self.previous_plan is not None:
            total += 1
        return total

    @property
    def is_thin(self) -> bool:
        return self.evidence_count < 2 or (
            self.latest_metric is None and self.latest_plan is None and not self.diagnostics and not self.regressions
        )

    @property
    def signal_inventory(self) -> list[str]:
        signals: set[str] = {"fingerprint.normalized_query", "fingerprint.fingerprint_hash"}

        if self.metric_window:
            signals.update(
                {
                    "metric_window",
                    "trend.mean_exec_time_ms",
                    "trend.calls",
                    "trend.rows_returned",
                    "trend.temp_blks_written",
                }
            )

        if self.latest_plan is not None:
            signals.update(
                {
                    "plan.top_node_type",
                    "plan.uses_seq_scan",
                    "plan.uses_index_scan",
                    "plan.actual_rows",
                    "plan.estimated_rows",
                    "plan.row_estimate_ratio",
                    "plan.access_path_regression",
                }
            )
        if self.previous_plan is not None:
            signals.add("plan.previous_snapshot")

        for diag in self.diagnostics:
            signals.add(f"diagnostic.{diag.diagnostic_type}")
            signals.add(f"diagnostic.severity.{diag.severity}")

        for reg in self.regressions:
            signals.add(f"regression.{reg.regression_type}")
            signals.add(f"regression.severity.{reg.severity}")

        if self.focus_regression is not None:
            signals.add(f"regression.focus.{self.focus_regression.regression_type}")

        if self.placement_context is not None:
            signals.add("placement.simulation_context")

        return sorted(signals)

    @property
    def placement_context(self) -> dict[str, Any] | None:
        if not _placement_relevant(self.fingerprint.normalized_query):
            return None
        return {
            "relevant": True,
            "summary": (
                "No persisted placement simulation result is linked to this fingerprint. "
                "The synthetic what-if placement simulator stays separate from live query telemetry."
            ),
        }

    def compact_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fingerprint": self.fingerprint.model_dump(mode="json"),
            "evidence_count": self.evidence_count,
            "signal_inventory": self.signal_inventory,
            "query_preview": self.fingerprint.normalized_query[:240],
        }

        if self.metric_window:
            metrics = [m.model_dump(mode="json") for m in self.metric_window]
            payload["metric_window"] = metrics
            first = self.metric_window[0]
            last = self.metric_window[-1]
            start_mean = max(float(first.mean_exec_time_ms), 0.001)
            payload["metric_trend"] = {
                "samples": len(metrics),
                "first_captured_at": first.captured_at.isoformat(),
                "latest_captured_at": last.captured_at.isoformat(),
                "first_mean_exec_time_ms": first.mean_exec_time_ms,
                "latest_mean_exec_time_ms": last.mean_exec_time_ms,
                "mean_exec_time_ratio": round(float(last.mean_exec_time_ms) / start_mean, 2),
                "calls_delta": last.calls - first.calls,
                "rows_returned_delta": last.rows_returned - first.rows_returned,
                "temp_blks_written_delta": last.temp_blks_written - first.temp_blks_written,
            }

        if self.latest_plan is not None:
            payload["latest_plan"] = self.latest_plan.model_dump(mode="json")
        if self.previous_plan is not None:
            payload["previous_plan"] = self.previous_plan.model_dump(mode="json")
            payload["plan_diff_summary"] = self.plan_diff_summary()
        if self.diagnostics:
            payload["diagnostics"] = [d.model_dump(mode="json") for d in self.diagnostics]
        if self.regressions:
            payload["regressions"] = [r.model_dump(mode="json") for r in self.regressions]
        if self.focus_regression is not None:
            payload["focus_regression"] = self.focus_regression.model_dump(mode="json")
        if self.placement_context is not None:
            payload["placement_context"] = self.placement_context

        return payload

    def plan_diff_summary(self) -> dict[str, Any] | None:
        if self.latest_plan is None or self.previous_plan is None:
            return None

        previous_shape = self.previous_plan.top_node_type
        current_shape = self.latest_plan.top_node_type
        access_path_delta = None
        if self.previous_plan.uses_index_scan and self.latest_plan.uses_seq_scan:
            access_path_delta = "index-assisted access regressed to sequential scan"
        elif not self.previous_plan.uses_seq_scan and self.latest_plan.uses_seq_scan:
            access_path_delta = "planner shifted from index-assisted access to sequential scan"
        elif self.previous_plan.uses_seq_scan and self.latest_plan.uses_index_scan:
            access_path_delta = "planner recovered from sequential scan to index-assisted access"

        row_estimate_delta = None
        if self.previous_plan.actual_rows is not None and self.previous_plan.estimated_rows is not None:
            prev_ratio = self.previous_plan.actual_rows / max(self.previous_plan.estimated_rows, 1)
            if self.latest_plan.actual_rows is not None and self.latest_plan.estimated_rows is not None:
                latest_ratio = self.latest_plan.actual_rows / max(self.latest_plan.estimated_rows, 1)
                row_estimate_delta = f"row-estimate ratio moved from {prev_ratio:.2f}x to {latest_ratio:.2f}x"

        delta_parts = []
        if previous_shape != current_shape:
            delta_parts.append(f"top node changed from {previous_shape} to {current_shape}")
        if self.previous_plan.estimated_total_cost is not None and self.latest_plan.estimated_total_cost is not None:
            delta_parts.append(
                f"estimated cost moved from {self.previous_plan.estimated_total_cost:.1f} to {self.latest_plan.estimated_total_cost:.1f}"
            )
        if self.previous_plan.actual_rows is not None and self.latest_plan.actual_rows is not None:
            delta_parts.append(
                f"actual rows moved from {self.previous_plan.actual_rows} to {self.latest_plan.actual_rows}"
            )

        return {
            "previous_shape": previous_shape,
            "current_shape": current_shape,
            "plan_delta": "; ".join(delta_parts) if delta_parts else "plan structure changed between captures",
            "row_estimate_delta": row_estimate_delta,
            "access_path_delta": access_path_delta,
        }


def _get_fingerprint(session: Session, target_id: UUID) -> QueryFingerprint:
    fp = session.query(QueryFingerprint).filter_by(id=target_id).first()
    if fp is None:
        raise LookupError("query not found")
    return fp


def build_evidence_bundle(
    session: Session,
    *,
    query_id: UUID | None = None,
    fingerprint: UUID | None = None,
    regression_id: UUID | None = None,
) -> EvidenceBundle:
    if query_id is not None and fingerprint is not None and query_id != fingerprint:
        raise ValueError("query_id and fingerprint must refer to the same query")

    focus_regression: QueryRegression | None = None
    target_fingerprint: UUID | None = None

    if regression_id is not None:
        focus_regression = session.query(QueryRegression).filter_by(id=regression_id).first()
        if focus_regression is None:
            raise LookupError("regression not found")
        target_fingerprint = focus_regression.fingerprint_id

    target_fingerprint = target_fingerprint or query_id or fingerprint
    if target_fingerprint is None:
        raise ValueError("query_id, fingerprint, or regression_id is required")

    fp_row = _get_fingerprint(session, target_fingerprint)

    metric_rows = (
        session.query(QueryMetric)
        .filter_by(fingerprint_id=fp_row.id)
        .order_by(QueryMetric.captured_at.desc())
        .limit(6)
        .all()
    )
    metric_window = [MetricPoint.model_validate(row) for row in reversed(metric_rows)]

    plan_rows = (
        session.query(QueryPlan)
        .filter_by(fingerprint_id=fp_row.id)
        .order_by(QueryPlan.captured_at.desc())
        .limit(2)
        .all()
    )
    latest_plan = PlanSummary.model_validate(plan_rows[0]) if plan_rows else None
    previous_plan = PlanSummary.model_validate(plan_rows[1]) if len(plan_rows) > 1 else None

    diagnostics = [
        DiagnosticOut.model_validate(row)
        for row in (
            session.query(QueryDiagnostic)
            .filter_by(fingerprint_id=fp_row.id)
            .order_by(QueryDiagnostic.created_at.desc())
            .limit(8)
            .all()
        )
    ]

    regressions = [
        RegressionOut.model_validate(row)
        for row in (
            session.query(QueryRegression)
            .filter_by(fingerprint_id=fp_row.id)
            .order_by(QueryRegression.created_at.desc())
            .limit(8)
            .all()
        )
    ]

    focus = RegressionOut.model_validate(focus_regression) if focus_regression is not None else None

    return EvidenceBundle(
        fingerprint=FingerprintOut.model_validate(fp_row),
        metric_window=metric_window,
        latest_plan=latest_plan,
        previous_plan=previous_plan,
        diagnostics=diagnostics,
        regressions=regressions,
        focus_regression=focus,
    )


def bundle_from_payload(payload: dict[str, Any]) -> EvidenceBundle:
    fingerprint = FingerprintOut.model_validate(payload["fingerprint"])
    metric_window = [MetricPoint.model_validate(item) for item in payload.get("metric_window", [])]
    latest_plan = (
        PlanSummary.model_validate(payload["latest_plan"]) if payload.get("latest_plan") is not None else None
    )
    previous_plan = (
        PlanSummary.model_validate(payload["previous_plan"]) if payload.get("previous_plan") is not None else None
    )
    diagnostics = [
        DiagnosticOut.model_validate(item)
        for item in payload.get("diagnostics", [])
    ]
    regressions = [
        RegressionOut.model_validate(item)
        for item in payload.get("regressions", [])
    ]
    focus_regression = (
        RegressionOut.model_validate(payload["focus_regression"])
        if payload.get("focus_regression") is not None
        else None
    )

    return EvidenceBundle(
        fingerprint=fingerprint,
        metric_window=metric_window,
        latest_plan=latest_plan,
        previous_plan=previous_plan,
        diagnostics=diagnostics,
        regressions=regressions,
        focus_regression=focus_regression,
    )
