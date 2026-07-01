from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from app.core.diagnostics import diagnose_query

FIX = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIX / name).read_text())


def test_diagnostics_detect_seq_scan_fallback_and_row_mismatch():
    prev_plan = SimpleNamespace(uses_index_scan=True, uses_seq_scan=False, actual_rows=20, estimated_rows=20)
    latest_plan = SimpleNamespace(uses_index_scan=False, uses_seq_scan=True, actual_rows=2000, estimated_rows=50)
    metric = SimpleNamespace(rows_returned=2400)

    issues = diagnose_query(
        normalized_query="select * from demo.orders where shipping_zip = ?",
        latest_metric=metric,
        latest_plan=latest_plan,
        previous_plan=prev_plan,
        plan_json=_load("explain_seq_scan.json"),
    )

    types = {issue.diagnostic_type for issue in issues}
    assert "seq_scan_fallback" in types
    assert "row_estimate_mismatch" in types
    assert "missing_index_candidate" in types


def test_diagnostics_detect_nested_loop_and_spill():
    latest_plan = SimpleNamespace(uses_index_scan=True, uses_seq_scan=False, actual_rows=215, estimated_rows=200)
    issues = diagnose_query(
        normalized_query="select * from demo.events join demo.users on true",
        latest_metric=SimpleNamespace(rows_returned=215),
        latest_plan=latest_plan,
        previous_plan=None,
        plan_json=_load("explain_nested_loop.json"),
    )

    assert any(issue.diagnostic_type == "nested_loop_explosion" for issue in issues)

    spill_plan = [
        {
            "Plan": {
                "Node Type": "Sort",
                "Plan Rows": 10,
                "Actual Rows": 10,
                "Temp Read Blocks": 3,
                "Temp Written Blocks": 7,
                "Sort Space Used": 2048,
                "Plans": [],
            }
        }
    ]
    spill_issues = diagnose_query(
        normalized_query="select * from demo.events order by created_at",
        latest_metric=SimpleNamespace(rows_returned=10),
        latest_plan=SimpleNamespace(uses_index_scan=False, uses_seq_scan=True, actual_rows=10, estimated_rows=10),
        previous_plan=None,
        plan_json=spill_plan,
    )
    assert any(issue.diagnostic_type == "temp_sort_hash_spill" for issue in spill_issues)


def test_diagnostics_detect_vector_bypass():
    issues = diagnose_query(
        normalized_query="select * from demo.vector_items order by embedding <-> ? limit 10",
        latest_metric=SimpleNamespace(rows_returned=10),
        latest_plan=SimpleNamespace(uses_index_scan=False, uses_seq_scan=True, actual_rows=10, estimated_rows=10),
        previous_plan=SimpleNamespace(uses_index_scan=True, uses_seq_scan=False, actual_rows=10, estimated_rows=10),
        plan_json=_load("explain_seq_scan.json"),
    )

    assert any(issue.diagnostic_type == "vector_hnsw_bypass" for issue in issues)
