"""Pure parser over Postgres ``EXPLAIN (FORMAT JSON)`` output.

Walks the plan tree and returns deterministic facts the regression detector
and the UI can rely on. Tolerates the absence of ``Actual Rows`` /
``Execution Time`` so it works for both ANALYZE and non-ANALYZE plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field

INDEX_NODE_TYPES = frozenset({"Index Scan", "Index Only Scan", "Bitmap Index Scan"})


@dataclass
class ParsedNode:
    node_type: str
    relation_name: str | None
    estimated_rows: int | None
    actual_rows: int | None
    total_cost: float | None
    temp_read_blocks: int | None = None
    temp_written_blocks: int | None = None
    sort_space_used_kb: float | None = None
    sort_space_type: str | None = None
    hash_batches: int | None = None


@dataclass
class ParsedPlan:
    top_node_type: str | None
    uses_seq_scan: bool
    uses_index_scan: bool
    estimated_total_cost: float | None
    actual_rows: int | None
    estimated_rows: int | None
    planning_time_ms: float | None
    execution_time_ms: float | None
    nodes: list[ParsedNode] = field(default_factory=list)


def _walk(node: dict, acc: list[ParsedNode]) -> None:
    acc.append(
        ParsedNode(
            node_type=node.get("Node Type", ""),
            relation_name=node.get("Relation Name"),
            estimated_rows=node.get("Plan Rows"),
            actual_rows=node.get("Actual Rows"),
            total_cost=node.get("Total Cost"),
            temp_read_blocks=node.get("Temp Read Blocks"),
            temp_written_blocks=node.get("Temp Written Blocks"),
            sort_space_used_kb=node.get("Sort Space Used"),
            sort_space_type=node.get("Sort Space Type"),
            hash_batches=node.get("Hash Batches"),
        )
    )
    for child in node.get("Plans") or []:
        _walk(child, acc)


def parse_explain(plan_json: list | dict) -> ParsedPlan:
    if not plan_json:
        return ParsedPlan(
            top_node_type=None,
            uses_seq_scan=False,
            uses_index_scan=False,
            estimated_total_cost=None,
            actual_rows=None,
            estimated_rows=None,
            planning_time_ms=None,
            execution_time_ms=None,
        )

    root = plan_json[0] if isinstance(plan_json, list) else plan_json
    plan = root.get("Plan", root)

    nodes: list[ParsedNode] = []
    _walk(plan, nodes)
    types = {n.node_type for n in nodes}

    return ParsedPlan(
        top_node_type=plan.get("Node Type"),
        uses_seq_scan="Seq Scan" in types,
        uses_index_scan=bool(types & INDEX_NODE_TYPES),
        estimated_total_cost=plan.get("Total Cost"),
        actual_rows=plan.get("Actual Rows"),
        estimated_rows=plan.get("Plan Rows"),
        planning_time_ms=root.get("Planning Time"),
        execution_time_ms=root.get("Execution Time"),
        nodes=nodes,
    )
