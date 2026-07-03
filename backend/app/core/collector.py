"""Collector: reads pg_stat_statements, fingerprints, stores metrics/plans,
detects regressions.  Designed to be called on-demand (POST /api/collect/run)
or from a scheduled job.

Safety rules
------------
- EXPLAIN is only run on safe SELECT/WITH queries.
- EXPLAIN ANALYZE is gated by ALLOW_EXPLAIN_ANALYZE env flag (default off).
- A per-query statement timeout prevents runaway EXPLAINs.
- pg_stat_statements normalises literals to ``$N`` placeholders. We handle
  these via PREPARE / EXPLAIN EXECUTE (default param value = 1), which lets
  the planner use real table statistics while still being safe.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.core.diagnostics import diagnose_query, persist_diagnostics
from app.core.explain_parser import ParsedPlan, parse_explain
from app.core.fingerprint import fingerprint
from app.core.regression_detector import (
    MetricSnapshot,
    PlanSnapshot,
    detect_regressions,
)
from app.models import QueryFingerprint, QueryMetric, QueryPlan, QueryRegression
from app.observability.metrics import diagnostic_failures_total, diagnostic_latency_seconds

log = logging.getLogger(__name__)

_SELECT_START_RE = re.compile(r"^\s*(select|with)\b", re.I)
_DANGEROUS_KW_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|vacuum)\b",
    re.I,
)
_PG_PLACEHOLDER_RE = re.compile(r"\$\d+")
_FIND_PLACEHOLDERS_RE = re.compile(r"\$(\d+)")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _is_safe_select(sql: str) -> bool:
    s = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    s = re.sub(r"--[^\n]*", " ", s).strip()
    if not _SELECT_START_RE.match(s):
        return False
    if _DANGEROUS_KW_RE.search(s):
        return False
    return True


def _upsert_fingerprint(session: Session, norm: str, h: str) -> QueryFingerprint:
    fp = session.query(QueryFingerprint).filter_by(fingerprint_hash=h).first()
    if fp is None:
        fp = QueryFingerprint(fingerprint_hash=h, normalized_query=norm)
        session.add(fp)
        session.flush()
    else:
        from sqlalchemy import func
        fp.last_seen_at = func.now()
        session.flush()
    return fp


def _latest_metric(session: Session, fp_id: Any) -> QueryMetric | None:
    return (
        session.query(QueryMetric)
        .filter_by(fingerprint_id=fp_id)
        .order_by(QueryMetric.captured_at.desc())
        .first()
    )


def _latest_plan(session: Session, fp_id: Any) -> QueryPlan | None:
    return (
        session.query(QueryPlan)
        .filter_by(fingerprint_id=fp_id)
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )


def _metric_snapshot(m: QueryMetric) -> MetricSnapshot:
    return MetricSnapshot(
        calls=m.calls,
        mean_ms=m.mean_exec_time_ms,
        total_ms=m.total_exec_time_ms,
        rows=m.rows_returned,
        temp_blks_written=m.temp_blks_written,
    )


def _plan_snapshot(p: QueryPlan) -> PlanSnapshot:
    return PlanSnapshot(
        uses_seq_scan=p.uses_seq_scan,
        uses_index_scan=p.uses_index_scan,
        estimated_total_cost=p.estimated_total_cost,
        actual_rows=p.actual_rows,
        estimated_rows=p.estimated_rows,
        top_node_type=p.top_node_type,
    )


def _run_explain(
    session: Session, sql: str
) -> tuple[Any | None, ParsedPlan | None]:
    """Execute EXPLAIN and return (raw_json, ParsedPlan) or (None, None)."""
    timeout_ms = settings.EXPLAIN_TIMEOUT_MS
    has_placeholders = bool(_PG_PLACEHOLDER_RE.search(sql))

    # Build EXPLAIN statement
    analyze_opts = "(FORMAT JSON, ANALYZE, BUFFERS, TIMING OFF)" if settings.ALLOW_EXPLAIN_ANALYZE else "(FORMAT JSON)"

    try:
        if has_placeholders:
            # pg_stat_statements uses $N — use PREPARE/EXPLAIN EXECUTE
            nums = sorted({int(n) for n in _FIND_PLACEHOLDERS_RE.findall(sql)})
            max_n = max(nums) if nums else 1
            # Pass '1' as the default value for every parameter (integer literal
            # is coerced by Postgres; the planner uses table stats regardless)
            params_str = ", ".join(["1"] * max_n)
            plan_name = f"ql_{abs(hash(sql)) % 99999:05d}"

            with session.begin_nested():
                session.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}ms'"))
                try:
                    session.execute(text(f"PREPARE {plan_name} AS {sql}"))
                    result = session.execute(
                        text(f"EXPLAIN {analyze_opts} EXECUTE {plan_name}({params_str})")
                    ).scalar_one()
                    session.execute(text(f"DEALLOCATE {plan_name}"))
                except Exception:
                    # best-effort cleanup
                    try:
                        session.execute(text(f"DEALLOCATE {plan_name}"))
                    except Exception:
                        pass
                    raise
        else:
            with session.begin_nested():
                session.execute(text(f"SET LOCAL statement_timeout = '{timeout_ms}ms'"))
                result = session.execute(
                    text(f"EXPLAIN {analyze_opts} {sql}")
                ).scalar_one()

        parsed = parse_explain(result)
        return result, parsed

    except Exception as exc:
        log.debug("explain failed for query %.80r: %s", sql, exc)
        return None, None


# ---------------------------------------------------------------------------
# main entry point
# ---------------------------------------------------------------------------

PG_STAT_QUERY = """
SELECT
    queryid,
    query,
    calls,
    total_exec_time  AS total_exec_time,
    mean_exec_time   AS mean_exec_time,
    rows,
    shared_blks_hit,
    shared_blks_read,
    temp_blks_written
FROM pg_stat_statements
WHERE
    query NOT ILIKE '%pg_stat_statements%'
    AND query NOT ILIKE '%plantrace.%'
    AND query NOT ILIKE '%information_schema%'
    AND query NOT ILIKE '%PREPARE%'
    AND query NOT ILIKE '%EXPLAIN%'
    -- exclude SQLAlchemy / driver bookkeeping
    AND query NOT ILIKE '%savepoint%'
    AND query NOT ILIKE 'rollback%'
    AND query NOT ILIKE 'commit%'
    AND query NOT ILIKE 'begin%'
    AND query NOT ILIKE 'set %'
    AND query NOT ILIKE 'show %'
    AND query NOT ILIKE 'discard %'
    AND query NOT ILIKE 'deallocate%'
    -- exclude DDL noise from migrations/seed
    AND query NOT ILIKE 'create %'
    AND query NOT ILIKE 'drop %'
    AND query NOT ILIKE 'alter %'
    AND query NOT ILIKE 'truncate %'
    AND query NOT ILIKE 'analyze %'
    AND query NOT ILIKE 'vacuum%'
    AND mean_exec_time >= :min_mean
ORDER BY mean_exec_time DESC
"""


def run_collection(
    session: Session, *, run_explain: bool = True
) -> dict[str, int | float]:
    t0 = time.monotonic()
    counters: dict[str, int] = dict(fingerprints=0, metrics=0, plans=0, regressions=0, diagnostics=0)

    try:
        rows = session.execute(
            text(PG_STAT_QUERY), {"min_mean": settings.MIN_MEAN_MS}
        ).fetchall()
    except Exception as exc:
        log.error("failed to read pg_stat_statements: %s", exc)
        return {**counters, "duration_ms": 0.0}

    for row in rows:
        raw_sql: str = row.query or ""
        if not raw_sql.strip():
            continue

        norm, h = fingerprint(raw_sql)
        fp = _upsert_fingerprint(session, norm, h)
        counters["fingerprints"] += 1

        prev_m = _latest_metric(session, fp.id)
        prev_p = _latest_plan(session, fp.id)

        new_m = QueryMetric(
            fingerprint_id=fp.id,
            calls=int(row.calls or 0),
            total_exec_time_ms=float(row.total_exec_time or 0),
            mean_exec_time_ms=float(row.mean_exec_time or 0),
            rows_returned=int(row.rows or 0),
            shared_blks_hit=int(row.shared_blks_hit or 0),
            shared_blks_read=int(row.shared_blks_read or 0),
            temp_blks_written=int(row.temp_blks_written or 0),
        )
        session.add(new_m)
        session.flush()
        counters["metrics"] += 1

        new_p: QueryPlan | None = None
        plan_json = None
        if run_explain and _is_safe_select(raw_sql):
            plan_json, parsed = _run_explain(session, raw_sql)
            if plan_json is not None and parsed is not None:
                new_p = QueryPlan(
                    fingerprint_id=fp.id,
                    plan_json=plan_json,
                    planning_time_ms=parsed.planning_time_ms,
                    execution_time_ms=parsed.execution_time_ms,
                    top_node_type=parsed.top_node_type,
                    uses_seq_scan=parsed.uses_seq_scan,
                    uses_index_scan=parsed.uses_index_scan,
                    estimated_total_cost=parsed.estimated_total_cost,
                    actual_rows=parsed.actual_rows,
                    estimated_rows=parsed.estimated_rows,
                )
                session.add(new_p)
                session.flush()
                counters["plans"] += 1

        prev_ms = _metric_snapshot(prev_m) if prev_m else None
        new_ms = _metric_snapshot(new_m)
        prev_ps = _plan_snapshot(prev_p) if prev_p else None
        new_ps = _plan_snapshot(new_p) if new_p else None

        regs = detect_regressions(prev_ms, new_ms, prev_ps, new_ps)
        for r in regs:
            session.add(
                QueryRegression(
                    fingerprint_id=fp.id,
                    severity=r["severity"],
                    regression_type=r["regression_type"],
                    message=r["message"],
                    old_metric_json=r["old_metric_json"],
                    new_metric_json=r["new_metric_json"],
                )
            )
            counters["regressions"] += 1

        diag_t0 = time.perf_counter()
        try:
            issues = diagnose_query(
                normalized_query=fp.normalized_query,
                latest_metric=new_m,
                latest_plan=new_p,
                previous_plan=prev_p,
                plan_json=plan_json,
            )
        except Exception:
            diagnostic_failures_total.inc()
            issues = []
        diagnostic_latency_seconds.labels(source="collector").observe(time.perf_counter() - diag_t0)
        if issues:
            persist_diagnostics(session, fingerprint_id=fp.id, plan_id=getattr(new_p, "id", None), issues=issues)
            counters["diagnostics"] += len(issues)

    session.commit()
    elapsed_ms = (time.monotonic() - t0) * 1000
    return {**counters, "duration_ms": round(elapsed_ms, 1)}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        result = run_collection(session)
        log.info("collection done: %s", result)
    finally:
        session.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
