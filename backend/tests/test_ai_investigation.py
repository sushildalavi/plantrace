from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.deps as deps_mod
import app.config as cfg_mod
import app.database as db_mod
from app.ai.evidence import EvidenceBundle, build_evidence_bundle
from app.ai.heuristics import build_heuristic_report
from app.ai.providers import FakeProvider
from app.ai.service import QueryRegressionInvestigator
from app.main import app
from app.models import QueryDiagnostic, QueryFingerprint, QueryMetric, QueryPlan, QueryRegression
from app.schemas import QueryInvestigationOut


def _fingerprint_hash(sql: str) -> str:
    return hashlib.sha256(sql.lower().encode("utf-8")).hexdigest()


def _seed_bundle(
    db_session,
    *,
    thin: bool = False,
    placement: bool = False,
    tag: str | None = None,
) -> EvidenceBundle:
    tag = tag or uuid4().hex
    query = (
        f"SELECT * FROM tenant_usage WHERE tenant_id = $1 ORDER BY created_at DESC /* {tag} */"
        if placement
        else f"SELECT * FROM orders WHERE user_id = $1 ORDER BY created_at DESC /* {tag} */"
    )
    now = datetime.now(UTC)
    fp = QueryFingerprint(
        id=uuid4(),
        fingerprint_hash=_fingerprint_hash(query),
        normalized_query=query.lower(),
        first_seen_at=now - timedelta(hours=2),
        last_seen_at=now,
    )
    db_session.add(fp)

    if not thin:
        metrics = [
            QueryMetric(
                id=uuid4(),
                fingerprint_id=fp.id,
                captured_at=now - timedelta(minutes=20),
                ingested_at=now - timedelta(minutes=20),
                calls=100,
                total_exec_time_ms=120.0,
                mean_exec_time_ms=1.2,
                rows_returned=250,
                shared_blks_hit=100,
                shared_blks_read=12,
                temp_blks_written=0,
            ),
            QueryMetric(
                id=uuid4(),
                fingerprint_id=fp.id,
                captured_at=now - timedelta(minutes=10),
                ingested_at=now - timedelta(minutes=10),
                calls=120,
                total_exec_time_ms=240.0,
                mean_exec_time_ms=2.0,
                rows_returned=275,
                shared_blks_hit=120,
                shared_blks_read=18,
                temp_blks_written=5,
            ),
            QueryMetric(
                id=uuid4(),
                fingerprint_id=fp.id,
                captured_at=now,
                ingested_at=now,
                calls=140,
                total_exec_time_ms=840.0,
                mean_exec_time_ms=7.2,
                rows_returned=300,
                shared_blks_hit=90,
                shared_blks_read=40,
                temp_blks_written=25,
            ),
        ]
        db_session.add_all(metrics)

        prev_plan = QueryPlan(
            id=uuid4(),
            fingerprint_id=fp.id,
            captured_at=now - timedelta(minutes=10),
            plan_json={"Plan": {"Node Type": "Index Scan"}},
            planning_time_ms=0.5,
            execution_time_ms=2.3,
            top_node_type="Index Scan",
            uses_seq_scan=False,
            uses_index_scan=True,
            estimated_total_cost=120.0,
            actual_rows=220,
            estimated_rows=180,
        )
        latest_plan = QueryPlan(
            id=uuid4(),
            fingerprint_id=fp.id,
            captured_at=now,
            plan_json={"Plan": {"Node Type": "Seq Scan"}},
            planning_time_ms=0.6,
            execution_time_ms=12.5,
            top_node_type="Seq Scan",
            uses_seq_scan=True,
            uses_index_scan=False,
            estimated_total_cost=500.0,
            actual_rows=2200,
            estimated_rows=140,
        )
        db_session.add_all([prev_plan, latest_plan])
        db_session.flush()

        db_session.add(
            QueryDiagnostic(
                id=uuid4(),
                fingerprint_id=fp.id,
                plan_id=latest_plan.id,
                diagnostic_type="row_estimate_mismatch",
                severity="medium",
                title="Row estimate diverges from reality",
                explanation="The optimizer estimated far fewer rows than it observed.",
                suggested_action="Refresh statistics and inspect selectivity.",
                evidence_json={"ratio": 15.7},
                created_at=now,
            )
        )
        db_session.add(
            QueryRegression(
                id=uuid4(),
                fingerprint_id=fp.id,
                severity="high",
                regression_type="latency_spike",
                old_metric_json={"mean_exec_time_ms": 1.2},
                new_metric_json={"mean_exec_time_ms": 7.2},
                message="Mean latency jumped after the last capture.",
                created_at=now,
            )
        )

    db_session.flush()
    return build_evidence_bundle(db_session, query_id=fp.id)


def _build_fake_service(response_text: str, timeout_seconds: float = 2.0) -> QueryRegressionInvestigator:
    return QueryRegressionInvestigator(
        providers=[FakeProvider(response=response_text)],
        timeout_seconds=timeout_seconds,
    )


def test_fake_provider_success(db_session):
    bundle = _seed_bundle(db_session)
    response = _build_fake_service(
        build_heuristic_report(bundle).model_dump_json()
    ).investigate_bundle(bundle=bundle)

    assert response.source == "llm"
    assert response.grounded is True
    assert response.report.insufficient_evidence is False
    assert response.report.evidence
    assert response.provider == "fake"
    assert response.report.root_cause
    assert response.report.evidence_citations
    assert response.report.index_recommendation is not None


def test_invalid_json_from_model_falls_back(db_session):
    bundle = _seed_bundle(db_session)
    response = _build_fake_service("not-json").investigate_bundle(bundle=bundle)

    assert response.source == "heuristic"
    assert response.report.summary
    assert response.grounded is True


def test_timeout_falls_back(db_session):
    bundle = _seed_bundle(db_session)
    service = QueryRegressionInvestigator(
        providers=[FakeProvider(response=build_heuristic_report(bundle).model_dump_json(), delay_seconds=0.2)],
        timeout_seconds=0.05,
    )
    response = service.investigate_bundle(bundle=bundle)

    assert response.source == "heuristic"
    assert response.report.summary


def test_insufficient_evidence_returns_flagged_report(db_session):
    bundle = _seed_bundle(db_session, thin=True)
    response = QueryRegressionInvestigator(timeout_seconds=2).investigate_bundle(bundle=bundle)

    assert response.source == "insufficient"
    assert response.report.insufficient_evidence is True
    assert response.report.confidence <= 0.35


def test_schema_validation_falls_back(db_session):
    bundle = _seed_bundle(db_session)
    invalid = build_heuristic_report(bundle).model_copy(update={"confidence": 1.5}).model_dump_json()
    response = _build_fake_service(invalid).investigate_bundle(bundle=bundle)

    assert response.source == "heuristic"
    assert response.report.confidence <= 1.0


def test_grounding_check_rejects_unsupported_claims(db_session):
    bundle = _seed_bundle(db_session)
    payload = {
        "summary": "A production cluster issue was confirmed.",
        "risk_level": "high",
        "confidence": 0.92,
        "likely_causes": ["Production cluster saturation"],
        "evidence": [
            {
                "signal": "unsupported.signal",
                "observed_value": "made-up value",
                "why_it_matters": "This does not map to the bundle.",
            },
            {
                "signal": "another.unsupported.signal",
                "observed_value": "made-up value 2",
                "why_it_matters": "This also does not map to the bundle.",
            },
        ],
        "suggested_actions": ["Scale the production cluster immediately"],
        "insufficient_evidence": False,
    }
    response = _build_fake_service(
        QueryInvestigationOut.model_validate(payload).model_dump_json()
    ).investigate_bundle(bundle=bundle)

    assert response.source == "heuristic"
    assert response.insufficient_reason is not None


def test_heuristic_report_includes_plan_diff_and_priority(db_session):
    bundle = _seed_bundle(db_session)
    report = build_heuristic_report(bundle)

    assert report.explain_diff_summary is not None
    assert report.affected_query_fingerprint_summary
    assert report.remediation_priority in {"p0", "p1", "p2", "p3"}


def test_api_endpoint_uses_fake_service(db_session):
    bundle = _seed_bundle(db_session)
    db_session.commit()
    service = _build_fake_service(build_heuristic_report(bundle).model_dump_json())

    db_url = db_session.bind.url.render_as_string(hide_password=False).replace("psycopg2", "psycopg")
    os.environ["DATABASE_URL"] = db_url
    cfg_mod.settings = cfg_mod.Settings()
    db_mod.engine = create_engine(db_url, pool_pre_ping=True, future=True)
    db_mod.SessionLocal = sessionmaker(bind=db_mod.engine, autoflush=False, expire_on_commit=False)
    deps_mod.SessionLocal = sessionmaker(bind=db_mod.engine, autoflush=False, expire_on_commit=False)
    app.state.investigator_service = service

    with TestClient(app) as client:
        response = client.post("/api/ai/query-investigation", json={"query_id": str(bundle.fingerprint.id)})

    assert response.status_code == 200
    body = response.json()
    assert body["report"]["summary"]
    assert body["provider"] == "fake"


def test_workflow_nodes_execute_in_order(db_session):
    bundle = _seed_bundle(db_session)
    trace: list[str] = []

    class TracingInvestigator(QueryRegressionInvestigator):
        def _collect_query_evidence(self, state):
            trace.append("collect_query_evidence")
            return super()._collect_query_evidence(state)

        def _summarize_regression_signals(self, state):
            trace.append("summarize_regression_signals")
            return super()._summarize_regression_signals(state)

        def _run_llm_investigation(self, state):
            trace.append("run_llm_investigation")
            return super()._run_llm_investigation(state)

        def _validate_report_schema(self, state):
            trace.append("validate_report_schema")
            return super()._validate_report_schema(state)

        def _check_evidence_grounding(self, state):
            trace.append("check_evidence_grounding")
            return super()._check_evidence_grounding(state)

        def _persist_or_return_report(self, state):
            trace.append("persist_or_return_report")
            return super()._persist_or_return_report(state)

    service = TracingInvestigator(
        providers=[FakeProvider(response=build_heuristic_report(bundle).model_dump_json())],
        timeout_seconds=2,
    )
    response = service.investigate_bundle(bundle=bundle)

    assert response.report.summary
    assert trace == [
        "collect_query_evidence",
        "summarize_regression_signals",
        "run_llm_investigation",
        "validate_report_schema",
        "check_evidence_grounding",
        "persist_or_return_report",
    ]
