from __future__ import annotations

from app.models import QueryFingerprint, QueryMetric
from app.streaming.ingest import event_id_for, ingest_query_event


def test_ingest_query_event_persists_snapshot(db_session):
    event = {
        "database_name": "plantrace",
        "environment": "test",
        "service_id": "collector-test",
        "query_fingerprint": "abc123",
        "normalized_sql": "select * from demo.orders where user_id = ?",
        "calls": 10,
        "total_exec_time_ms": 100.0,
        "mean_exec_time_ms": 10.0,
        "rows": 10,
        "shared_blks_hit": 1,
        "shared_blks_read": 1,
        "temp_blks_written": 0,
        "is_vector_query": False,
        "captured_at": "2026-05-26T00:00:00Z",
    }

    out = ingest_query_event(db_session, event)
    db_session.commit()

    assert out == "inserted"
    assert db_session.query(QueryFingerprint).filter_by(fingerprint_hash="abc123").count() == 1
    assert db_session.query(QueryMetric).filter_by(event_id=event_id_for(event)).count() == 1


def test_ingest_query_event_duplicate_is_skipped(db_session):
    event = {
        "database_name": "plantrace",
        "environment": "test",
        "service_id": "collector-test",
        "query_fingerprint": "dup-fp-1",
        "normalized_sql": "select * from demo.orders where user_id = ?",
        "calls": 10,
        "total_exec_time_ms": 100.0,
        "mean_exec_time_ms": 10.0,
        "rows": 10,
        "shared_blks_hit": 1,
        "shared_blks_read": 1,
        "temp_blks_written": 0,
        "is_vector_query": False,
        "captured_at": "2026-05-26T00:00:00Z",
    }

    first = ingest_query_event(db_session, event)
    db_session.commit()
    second = ingest_query_event(db_session, event)
    db_session.commit()

    assert first == "inserted"
    assert second == "duplicate"
    assert db_session.query(QueryMetric).filter_by(event_id=event_id_for(event)).count() == 1
