from app.core.regression_detector import (
    MetricSnapshot,
    PlanSnapshot,
    detect_regressions,
)


def _m(mean_ms=10.0, calls=100, temp=0):
    return MetricSnapshot(
        calls=calls, mean_ms=mean_ms, total_ms=mean_ms * calls, rows=calls, temp_blks_written=temp
    )


def _p(seq=False, idx=True, cost=10.0, actual=10, est=10, top="Index Scan"):
    return PlanSnapshot(
        uses_seq_scan=seq,
        uses_index_scan=idx,
        estimated_total_cost=cost,
        actual_rows=actual,
        estimated_rows=est,
        top_node_type=top,
    )


def test_regression_no_previous_metric_returns_empty():
    out = detect_regressions(None, _m(), None, _p())
    assert out == []


def test_regression_no_new_metric_returns_empty():
    out = detect_regressions(_m(), None, _p(), _p())
    assert out == []


def test_regression_latency_spike():
    out = detect_regressions(_m(mean_ms=10.0), _m(mean_ms=22.0), _p(), _p())
    types = [r["regression_type"] for r in out]
    assert "latency_spike" in types
    assert "severe_latency_spike" not in types


def test_regression_severe_latency_only():
    out = detect_regressions(_m(mean_ms=10.0), _m(mean_ms=55.0), _p(), _p())
    types = [r["regression_type"] for r in out]
    assert types.count("severe_latency_spike") == 1
    assert "latency_spike" not in types
    severe = next(r for r in out if r["regression_type"] == "severe_latency_spike")
    assert severe["severity"] == "high"


def test_regression_index_to_seq_scan():
    prev_plan = _p(seq=False, idx=True, top="Index Scan")
    new_plan = _p(seq=True, idx=False, top="Seq Scan")
    out = detect_regressions(_m(mean_ms=10.0), _m(mean_ms=12.0), prev_plan, new_plan)
    types = [r["regression_type"] for r in out]
    assert "index_scan_to_seq_scan" in types
    rec = next(r for r in out if r["regression_type"] == "index_scan_to_seq_scan")
    assert rec["severity"] == "high"
    assert "index scan" in rec["message"].lower()
    assert "sequential scan" in rec["message"].lower()


def test_regression_row_estimate_mismatch():
    new_plan = _p(seq=True, idx=False, actual=2000, est=50, top="Seq Scan")
    out = detect_regressions(_m(), _m(), _p(seq=True, idx=False, top="Seq Scan"), new_plan)
    types = [r["regression_type"] for r in out]
    assert "row_estimate_mismatch" in types


def test_regression_row_estimate_within_threshold_skips():
    new_plan = _p(actual=80, est=50)
    out = detect_regressions(_m(), _m(), _p(), new_plan)
    types = [r["regression_type"] for r in out]
    assert "row_estimate_mismatch" not in types


def test_regression_temp_spill():
    out = detect_regressions(_m(temp=100), _m(temp=2000), _p(), _p())
    types = [r["regression_type"] for r in out]
    assert "temp_spill" in types


def test_regression_call_spike_low_severity():
    out = detect_regressions(_m(calls=10), _m(calls=30), _p(), _p())
    types = [r["regression_type"] for r in out]
    assert "call_spike" in types
    rec = next(r for r in out if r["regression_type"] == "call_spike")
    assert rec["severity"] == "low"


def test_regression_call_spike_suppressed_by_severe_latency():
    out = detect_regressions(_m(mean_ms=10.0, calls=10), _m(mean_ms=55.0, calls=30), _p(), _p())
    types = [r["regression_type"] for r in out]
    assert "severe_latency_spike" in types
    assert "call_spike" not in types


def test_regression_cost_spike():
    prev_plan = _p(cost=100.0)
    new_plan = _p(cost=300.0)
    out = detect_regressions(_m(), _m(), prev_plan, new_plan)
    types = [r["regression_type"] for r in out]
    assert "cost_spike" in types


def test_regression_zero_prev_mean_does_not_crash():
    out = detect_regressions(_m(mean_ms=0.0), _m(mean_ms=5.0), _p(), _p())
    types = [r["regression_type"] for r in out]
    assert "latency_spike" not in types
    assert "severe_latency_spike" not in types


def test_regression_includes_metric_snapshots():
    out = detect_regressions(_m(mean_ms=10.0), _m(mean_ms=20.0), _p(), _p())
    rec = next(r for r in out if r["regression_type"] == "latency_spike")
    assert rec["old_metric_json"]["mean_ms"] == 10.0
    assert rec["new_metric_json"]["mean_ms"] == 20.0


def test_regression_vector_hnsw_bypass_critical():
    prev_plan = _p(seq=False, idx=True, top="Index Scan")
    new_plan = _p(seq=True, idx=False, top="Seq Scan")
    out = detect_regressions(_m(mean_ms=10.0), _m(mean_ms=12.0), prev_plan, new_plan, is_vector_query=True)
    rec = next(r for r in out if r["regression_type"] == "vector_hnsw_index_bypass")
    assert rec["severity"] == "critical"
