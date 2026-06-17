from __future__ import annotations

from types import SimpleNamespace

from app.core.recommendations import recommend_for_query


def test_recommend_for_query_flags_seq_scan_and_temp_spill():
    metric = SimpleNamespace(rows_returned=2500, temp_blks_written=7)
    plan = SimpleNamespace(uses_seq_scan=True, actual_rows=1200, estimated_rows=80)

    recs = recommend_for_query(
        normalized_query="SELECT * FROM events WHERE user_id = $1",
        latest_metric=metric,
        latest_plan=plan,
    )

    ids = {rec.id for rec in recs}
    assert "seq-scan-index-suggestion" in ids
    assert "temp-spill-memory-tuning" in ids
    assert "stale-statistics" in ids
    for rec in recs:
        assert rec.safe_sql is None


def test_recommend_for_query_flags_vector_regression():
    metric = SimpleNamespace(rows_returned=10, temp_blks_written=0)
    plan = SimpleNamespace(uses_seq_scan=True, actual_rows=None, estimated_rows=None)

    recs = recommend_for_query(
        normalized_query="SELECT * FROM embeddings ORDER BY embedding <=> $1 LIMIT 10",
        latest_metric=metric,
        latest_plan=plan,
        regression_type="vector_hnsw_index_bypass",
    )

    assert any(rec.id == "vector-index-compatibility" for rec in recs)


def test_recommend_for_query_deduplicates_results():
    metric = SimpleNamespace(rows_returned=3000, temp_blks_written=2)
    plan = SimpleNamespace(uses_seq_scan=True, actual_rows=5000, estimated_rows=100)

    recs = recommend_for_query(
        normalized_query="SELECT * FROM items WHERE category = $1",
        latest_metric=metric,
        latest_plan=plan,
        regression_type="latency_spike",
    )

    ids = [rec.id for rec in recs]
    assert len(ids) == len(set(ids))
