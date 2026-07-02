from __future__ import annotations

from dataclasses import dataclass

from app.ai.evidence import EvidenceBundle
from app.schemas import (
    EvidenceCitation,
    ExplainDiffSummary,
    IndexRecommendation,
    InvestigationEvidenceOut,
    QueryInvestigationOut,
    QueryRewriteSuggestion,
)


def _add_evidence(
    items: list[InvestigationEvidenceOut],
    seen: set[str],
    signal: str,
    observed_value: str,
    why_it_matters: str,
    limit: int = 6,
) -> None:
    if signal in seen or len(items) >= limit:
        return
    items.append(
        InvestigationEvidenceOut(
            signal=signal,
            observed_value=observed_value,
            why_it_matters=why_it_matters,
        )
    )
    seen.add(signal)


def _append_query_preview(bundle: EvidenceBundle, items: list[InvestigationEvidenceOut], seen: set[str]) -> None:
    _add_evidence(
        items,
        seen,
        "fingerprint.normalized_query",
        bundle.fingerprint.normalized_query[:180],
        "This is the exact normalized statement being investigated.",
    )


def _latency_trend(bundle: EvidenceBundle) -> tuple[float | None, str | None]:
    if len(bundle.metric_window) < 2:
        return None, None
    first = bundle.metric_window[0]
    last = bundle.metric_window[-1]
    base = max(float(first.mean_exec_time_ms), 0.001)
    ratio = float(last.mean_exec_time_ms) / base
    return ratio, (
        f"mean_exec_time_ms rose from {first.mean_exec_time_ms:.2f} to "
        f"{last.mean_exec_time_ms:.2f} across {len(bundle.metric_window)} samples"
    )


def _severity_rank(severity: str) -> int:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return order.get(severity, 0)


@dataclass(slots=True)
class _NarrativeState:
    root_cause: str | None = None
    why_this_changed: str | None = None
    regression_timeline: str | None = None
    remediation_priority: str = "p2"


def _plan_shapes(bundle: EvidenceBundle) -> tuple[str | None, str | None]:
    prev = bundle.previous_plan.top_node_type if bundle.previous_plan else None
    curr = bundle.latest_plan.top_node_type if bundle.latest_plan else None
    return prev, curr


def _fingerprint_summary(bundle: EvidenceBundle) -> str:
    query = bundle.fingerprint.normalized_query.strip().replace("\n", " ")
    preview = query[:180]
    return f"{bundle.fingerprint.fingerprint_hash[:12]} · {preview}"


def _rewrite_for_vector(bundle: EvidenceBundle) -> QueryRewriteSuggestion:
    return QueryRewriteSuggestion(
        title="Use the vector index path directly",
        rationale="The plan shows a vector search query regressing to a sequential scan, so the workload likely lost the intended ANN access path.",
        sql="SELECT * FROM vector_items ORDER BY embedding <-> $1 LIMIT 20",
    )


def _rewrite_for_seq_scan(bundle: EvidenceBundle) -> QueryRewriteSuggestion:
    return QueryRewriteSuggestion(
        title="Make the predicate more selective",
        rationale="A sequential scan on a selective filter usually means the optimizer could not prove the predicate was narrow enough for the index.",
        sql=None,
    )


def _index_recommendation(bundle: EvidenceBundle) -> IndexRecommendation | None:
    query = bundle.fingerprint.normalized_query.lower()
    latest_plan = bundle.latest_plan
    if latest_plan is None:
        return None
    if "<->" in query or "<#>" in query or "<=>" in query:
        return IndexRecommendation(
            title="Retain or recreate the ANN vector index",
            rationale="Vector similarity queries should stay on a vector-aware index path; the latest telemetry shows a fallback to sequential scan.",
            operator_class="hnsw / vector_l2_ops",
            sql="CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_vector_items_embedding_hnsw ON vector_items USING hnsw (embedding vector_l2_ops);",
            confidence=0.96,
        )
    if latest_plan.uses_seq_scan or latest_plan.uses_index_scan is False:
        return IndexRecommendation(
            title="Evaluate a covering index for the filter key",
            rationale="The latest plan is sequential and the telemetry suggests the access path lost selectivity.",
            operator_class="btree",
            sql=None,
            confidence=0.84,
        )
    return None


def _explain_diff(bundle: EvidenceBundle) -> ExplainDiffSummary | None:
    diff = bundle.plan_diff_summary()
    if not diff:
        return None
    return ExplainDiffSummary.model_validate(diff)


def _citations_from_bundle(bundle: EvidenceBundle, items: list[InvestigationEvidenceOut]) -> list[EvidenceCitation]:
    citations: list[EvidenceCitation] = []
    for item in items:
        source = "telemetry"
        if item.signal.startswith("plan."):
            source = "explain"
        elif item.signal.startswith("diagnostic."):
            source = "diagnostic"
        elif item.signal.startswith("regression."):
            source = "regression"
        citations.append(
            EvidenceCitation(
                signal=item.signal,
                source=source,
                observed_value=item.observed_value,
                rationale=item.why_it_matters,
            )
        )
    if len(citations) > 8:
        return citations[:8]
    return citations


def build_heuristic_report(
    bundle: EvidenceBundle,
    *,
    reason: str | None = None,
) -> QueryInvestigationOut:
    items: list[InvestigationEvidenceOut] = []
    seen: set[str] = set()
    likely_causes: list[str] = []
    suggested_actions: list[str] = []
    strongest_risk = 0
    confidence = 0.12
    narrative = _NarrativeState()

    _append_query_preview(bundle, items, seen)

    trend_ratio, trend_text = _latency_trend(bundle)
    if trend_ratio is not None and trend_text is not None:
        _add_evidence(
            items,
            seen,
            "trend.mean_exec_time_ms",
            f"{trend_text} ({trend_ratio:.2f}x)",
            "A sustained latency increase is the first clue that the access path or cardinality assumptions changed.",
        )
        if trend_ratio >= 1.5:
            likely_causes.append("Latency is trending upward across the captured metric window.")
            suggested_actions.append("Compare the latest plan with the previous capture and confirm the plan shape did not regress.")
            strongest_risk = max(strongest_risk, 2)
            confidence += 0.18
            narrative.regression_timeline = trend_text
        if trend_ratio >= 3.0:
            strongest_risk = max(strongest_risk, 3)
            confidence += 0.1

    latest_plan = bundle.latest_plan
    previous_plan = bundle.previous_plan
    if latest_plan is not None:
        _add_evidence(
            items,
            seen,
            "plan.uses_seq_scan",
            str(latest_plan.uses_seq_scan).lower(),
            "A sequential scan on a query that used to be selective often points to an access-path regression.",
        )
        _add_evidence(
            items,
            seen,
            "plan.uses_index_scan",
            str(latest_plan.uses_index_scan).lower(),
            "If the planner is no longer using an index, the query may have lost a selective access path.",
        )
        if latest_plan.top_node_type:
            _add_evidence(
                items,
                seen,
                "plan.top_node_type",
                latest_plan.top_node_type,
                "The top node hints at the overall plan shape chosen by the optimizer.",
            )
        if latest_plan.actual_rows is not None and latest_plan.estimated_rows is not None:
            est = max(float(latest_plan.estimated_rows), 1.0)
            ratio = float(latest_plan.actual_rows) / est
            _add_evidence(
                items,
                seen,
                "plan.row_estimate_ratio",
                f"{latest_plan.actual_rows} actual vs {latest_plan.estimated_rows} estimated ({ratio:.2f}x)",
                "Cardinality mismatches are a common trigger for bad join order and access-path choices.",
            )
            if ratio >= 10.0:
                likely_causes.append("Row estimates are badly off, which can mislead the optimizer.")
                suggested_actions.append("Refresh statistics and inspect predicates or multi-column selectivity.")
                strongest_risk = max(strongest_risk, 2)
                confidence += 0.16
            elif ratio >= 3.0:
                strongest_risk = max(strongest_risk, 1)
                confidence += 0.08

        if previous_plan is not None and previous_plan.uses_index_scan and latest_plan.uses_seq_scan:
            _add_evidence(
                items,
                seen,
                "plan.access_path_regression",
                "index-assisted access in the previous capture, sequential scan in the latest capture",
                "A plan flip like this often accompanies a planner regression or changed predicate selectivity.",
            )
            likely_causes.append("The query regressed from index-assisted access to a sequential scan.")
            suggested_actions.append("Compare indexes, predicates, and statistics between the previous and latest captures.")
            strongest_risk = max(strongest_risk, 3)
            confidence += 0.2
            narrative.root_cause = "The optimizer flipped from index-assisted access to a sequential scan."
            narrative.why_this_changed = "The latest capture no longer trusts the previous access path and row estimates diverged."
        elif latest_plan.uses_seq_scan:
            likely_causes.append("The latest plan is relying on a sequential scan.")
            suggested_actions.append("Confirm whether an index could support the selective predicate or join key.")
            strongest_risk = max(strongest_risk, 2)
            confidence += 0.12
            narrative.root_cause = "The query lost a selective access path and is scanning more rows."

    for diag in bundle.diagnostics:
        _add_evidence(
            items,
            seen,
            f"diagnostic.{diag.diagnostic_type}",
            f"{diag.severity}: {diag.title}",
            diag.explanation,
        )
        if diag.suggested_action:
            suggested_actions.append(diag.suggested_action)
        if diag.diagnostic_type in {"vector_hnsw_bypass", "seq_scan_fallback"}:
            strongest_risk = max(strongest_risk, 3)
            confidence += 0.16
            if "vector" in diag.diagnostic_type:
                narrative.root_cause = "Vector search fell off the ANN path and reverted to a sequential scan."
            else:
                narrative.root_cause = "A selective access path regressed into sequential scanning."
        elif diag.diagnostic_type in {"row_estimate_mismatch", "temp_sort_hash_spill", "missing_index_candidate"}:
            strongest_risk = max(strongest_risk, 2)
            confidence += 0.12
        likely_causes.append(diag.title)

    for reg in bundle.regressions:
        _add_evidence(
            items,
            seen,
            f"regression.{reg.regression_type}",
            f"{reg.severity}: {reg.message}",
            "Recent regression records confirm that the slowdown was observed repeatedly.",
        )
        if reg.severity in {"critical", "high"}:
            strongest_risk = max(strongest_risk, _severity_rank(reg.severity))
            confidence += 0.15
        likely_causes.append(reg.message)

    if bundle.focus_regression is not None:
        _add_evidence(
            items,
            seen,
            f"regression.focus.{bundle.focus_regression.regression_type}",
            bundle.focus_regression.message,
            "The requested regression record is the most direct evidence for this investigation.",
        )
        if not narrative.root_cause:
            narrative.root_cause = bundle.focus_regression.message

    placement_context = bundle.placement_context
    if placement_context is not None:
        _add_evidence(
            items,
            seen,
            "placement.simulation_context",
            placement_context["summary"],
            "This query touches placement language, but any placement analysis remains synthetic and separate from live control.",
        )

    if not items:
        _append_query_preview(bundle, items, seen)

    if not likely_causes:
        if bundle.is_thin:
            likely_causes.append("Not enough telemetry history to isolate a dependable root cause.")
            narrative.remediation_priority = "p3"
        else:
            likely_causes.append("The evidence set is not pointing to a single dominant failure mode yet.")

    risk_level = "low"
    if strongest_risk >= 3:
        risk_level = "high"
        narrative.remediation_priority = "p0"
    elif strongest_risk >= 2:
        risk_level = "medium"
        narrative.remediation_priority = "p1"

    if bundle.is_thin:
        risk_level = "low" if risk_level == "low" else risk_level
        confidence = min(confidence, 0.35)
        suggested_actions.append("Collect more plan and metric history before treating this as a confirmed regression.")
        narrative.remediation_priority = "p3"

    if reason:
        suggested_actions.insert(0, f"Heuristic fallback used because {reason}.")

    if not narrative.root_cause:
        narrative.root_cause = likely_causes[0] if likely_causes else "The available telemetry does not isolate a single dominant cause."

    prev_shape, curr_shape = _plan_shapes(bundle)
    explain_diff = _explain_diff(bundle)
    index_rec = _index_recommendation(bundle)
    rewrite = _rewrite_for_vector(bundle) if index_rec and index_rec.operator_class else _rewrite_for_seq_scan(bundle)
    if index_rec and index_rec.operator_class and ("vector" in index_rec.operator_class or "<->" in bundle.fingerprint.normalized_query):
        rewrite = _rewrite_for_vector(bundle)

    summary_parts: list[str] = []
    if trend_text:
        summary_parts.append(trend_text)
    if latest_plan is not None:
        summary_parts.append(
            "latest plan uses "
            + ("a sequential scan" if latest_plan.uses_seq_scan else "an index-assisted access path")
        )
    if bundle.diagnostics:
        summary_parts.append(f"{len(bundle.diagnostics)} diagnostic finding(s) were already stored")
    if bundle.regressions:
        summary_parts.append(f"{len(bundle.regressions)} regression record(s) are available")

    if bundle.is_thin:
        summary = "Telemetry is too thin to isolate a dependable root cause."
        insufficient = True
    else:
        summary = "; ".join(summary_parts) if summary_parts else "The available telemetry does not isolate a single dominant cause."
        insufficient = False

    confidence = max(0.0, min(0.99, round(confidence + min(len(items) * 0.04, 0.24), 2)))
    likely_causes = list(dict.fromkeys(likely_causes))[:5]
    suggested_actions = list(dict.fromkeys(suggested_actions))[:5]
    evidence_citations = _citations_from_bundle(bundle, items)

    if explain_diff is not None and narrative.why_this_changed is None:
        narrative.why_this_changed = explain_diff.plan_delta
    if narrative.regression_timeline is None and bundle.metric_window:
        first = bundle.metric_window[0]
        last = bundle.metric_window[-1]
        narrative.regression_timeline = (
            f"Captured over {len(bundle.metric_window)} samples from {first.captured_at.isoformat()} to {last.captured_at.isoformat()}."
        )

    return QueryInvestigationOut(
        summary=summary,
        risk_level=risk_level,
        confidence=confidence,
        remediation_priority=narrative.remediation_priority,
        root_cause=narrative.root_cause,
        why_this_changed=narrative.why_this_changed,
        regression_timeline=narrative.regression_timeline,
        affected_query_fingerprint_summary=_fingerprint_summary(bundle),
        explain_diff_summary=explain_diff,
        query_rewrite_suggestion=rewrite,
        index_recommendation=index_rec,
        evidence_citations=evidence_citations,
        likely_causes=likely_causes,
        evidence=items[:6],
        suggested_actions=suggested_actions,
        unsupported_claims=[],
        insufficient_evidence=insufficient,
    )
