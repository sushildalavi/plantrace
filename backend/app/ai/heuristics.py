from __future__ import annotations

from app.ai.evidence import EvidenceBundle
from app.schemas import InvestigationEvidenceOut, QueryInvestigationOut


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
        elif latest_plan.uses_seq_scan:
            likely_causes.append("The latest plan is relying on a sequential scan.")
            suggested_actions.append("Confirm whether an index could support the selective predicate or join key.")
            strongest_risk = max(strongest_risk, 2)
            confidence += 0.12

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
        else:
            likely_causes.append("The evidence set is not pointing to a single dominant failure mode yet.")

    risk_level = "low"
    if strongest_risk >= 3:
        risk_level = "high"
    elif strongest_risk >= 2:
        risk_level = "medium"

    if bundle.is_thin:
        risk_level = "low" if risk_level == "low" else risk_level
        confidence = min(confidence, 0.35)
        suggested_actions.append("Collect more plan and metric history before treating this as a confirmed regression.")

    if reason:
        suggested_actions.insert(0, f"Heuristic fallback used because {reason}.")

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

    return QueryInvestigationOut(
        summary=summary,
        risk_level=risk_level,
        confidence=confidence,
        likely_causes=likely_causes,
        evidence=items[:6],
        suggested_actions=suggested_actions,
        insufficient_evidence=insufficient,
    )
