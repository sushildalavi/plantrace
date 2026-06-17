from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Recommendation:
    id: str
    title: str
    severity: str
    confidence: str
    explanation: str
    suggested_action: str
    evidence_fields: list[str]
    safe_sql: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def recommend_for_query(
    *,
    normalized_query: str,
    latest_metric: Any | None,
    latest_plan: Any | None,
    regression_type: str | None = None,
) -> list[Recommendation]:
    recs: list[Recommendation] = []
    query = normalized_query.lower()

    if latest_plan is not None and getattr(latest_plan, "uses_seq_scan", False):
        rows = getattr(latest_metric, "rows_returned", None)
        if " where " in query and rows is not None and rows >= 1000:
            recs.append(
                Recommendation(
                    id="seq-scan-index-suggestion",
                    title="Consider an index for the filtered column",
                    severity="medium",
                    confidence="medium",
                    explanation="The latest plan uses a sequential scan on a query with filtering and a high row count.",
                    suggested_action="Review whether an index on the filter column would reduce scan cost for this workload.",
                    evidence_fields=["uses_seq_scan", "rows_returned", "normalized_query"],
                )
            )

    if latest_metric is not None and getattr(latest_metric, "temp_blks_written", 0) > 0:
        recs.append(
            Recommendation(
                id="temp-spill-memory-tuning",
                title="Inspect sort/hash memory usage",
                severity="medium",
                confidence="medium",
                explanation="The latest execution wrote temp blocks, which often indicates spill pressure.",
                suggested_action="Inspect sort and hash memory usage, reduce result size, or tune work_mem cautiously.",
                evidence_fields=["temp_blks_written"],
            )
        )

    if regression_type == "vector_hnsw_index_bypass" or (
        latest_plan is not None
        and getattr(latest_plan, "uses_seq_scan", False)
        and "vector" in query
    ):
        recs.append(
            Recommendation(
                id="vector-index-compatibility",
                title="Check vector operator and index compatibility",
                severity="high",
                confidence="high",
                explanation="The query looks vector-oriented and the plan no longer appears to use index-assisted access.",
                suggested_action="Verify the vector operator, index type, and query shape are still compatible.",
                evidence_fields=["uses_seq_scan", "normalized_query", "regression_type"],
            )
        )

    if latest_plan is not None and getattr(latest_plan, "actual_rows", None) and getattr(latest_plan, "estimated_rows", None):
        actual = int(getattr(latest_plan, "actual_rows"))
        estimated = max(int(getattr(latest_plan, "estimated_rows")), 1)
        ratio = actual / estimated
        if ratio >= 10:
            recs.append(
                Recommendation(
                    id="stale-statistics",
                    title="Refresh statistics",
                    severity="medium",
                    confidence="medium",
                    explanation="The row estimate is far from the actual row count.",
                    suggested_action="Run ANALYZE or refresh table statistics before changing the query plan.",
                    evidence_fields=["actual_rows", "estimated_rows"],
                )
            )

    if latest_metric is not None and latest_plan is not None and regression_type == "latency_spike":
        recs.append(
            Recommendation(
                id="latency-spike-investigation",
                title="Investigate lock contention or cache effects",
                severity="low",
                confidence="low",
                explanation="Latency increased without a matching plan change signal in the current snapshot.",
                suggested_action="Check lock contention, cache misses, or upstream load before rewriting the query.",
                evidence_fields=["mean_exec_time_ms", "regression_type"],
            )
        )

    seen: set[str] = set()
    out: list[Recommendation] = []
    for rec in recs:
        if rec.id in seen:
            continue
        seen.add(rec.id)
        out.append(rec)
    return out
