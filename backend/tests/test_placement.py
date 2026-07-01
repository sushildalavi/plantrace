from __future__ import annotations

from app.core.placement import (
    NodeCapacity,
    PlacementScenario,
    ResourceVector,
    TenantWorkload,
    generate_synthetic_telemetry,
    run_algorithm,
    simulate_placement,
)


def _tenant(i: int) -> TenantWorkload:
    return TenantWorkload(
        tenant_id=f"tenant-{i}",
        database_name=f"tenant_db_{i}",
        region_preference="eastus",
        zone_affinity=None,
        normalized_sql="select * from invoices where tenant_id = ?",
        sql_fingerprint=f"fp-{i}",
        calls=1000 + i,
        mean_exec_time_ms=20.0 + i,
        p95_latency_ms=40.0 + i,
        resources=ResourceVector(cpu=20.0, memory=10.0, storage=15.0, iops=100.0, p95_latency_ms=40.0 + i),
        migration_cost=5.0 + i,
    )


def _scenario() -> PlacementScenario:
    nodes = [
        NodeCapacity(
            node_id="node-1",
            region="eastus",
            cluster_id="cluster-1",
            availability_zone="1",
            capacity=ResourceVector(cpu=200.0, memory=200.0, storage=200.0, iops=1000.0, p95_latency_ms=100.0),
        ),
        NodeCapacity(
            node_id="node-2",
            region="eastus",
            cluster_id="cluster-1",
            availability_zone="2",
            capacity=ResourceVector(cpu=200.0, memory=200.0, storage=200.0, iops=1000.0, p95_latency_ms=100.0),
        ),
    ]
    tenants = [_tenant(i) for i in range(1, 5)]
    return PlacementScenario(seed=7, regions=["eastus"], nodes=nodes, tenants=tenants)


def test_best_fit_balances_better_than_first_fit():
    scenario = _scenario()
    first_fit = run_algorithm(scenario, "first-fit")
    best_fit = run_algorithm(scenario, "greedy-best-fit")

    assert first_fit.comparison.balance_after > best_fit.comparison.balance_after
    assert best_fit.comparison.p95_decision_latency_ms >= 0
    assert len(first_fit.nodes[0].tenants) >= len(first_fit.nodes[1].tenants)
    assert len(best_fit.nodes[0].tenants) != len(best_fit.nodes[1].tenants) or best_fit.comparison.hotspot_reduction >= 0


def test_local_search_returns_simulation_shape():
    out = simulate_placement(seed=11, tenants=12, regions=2, clusters_per_region=2, nodes_per_cluster=2)

    assert out["seed"] == 11
    assert out["tenants"] == 12
    assert out["telemetry"]
    assert len(out["algorithms"]) == 4
    assert {algo["algorithm"] for algo in out["algorithms"]} == {
        "first-fit",
        "greedy-best-fit",
        "weighted-scoring",
        "local-search-rebalancer",
    }


def test_synthetic_telemetry_uses_fingerprints():
    telemetry = generate_synthetic_telemetry(seed=1, tenants=3)
    assert len(telemetry) == 3
    assert all(sample.sql_fingerprint for sample in telemetry)
    assert all("?" in sample.normalized_sql for sample in telemetry)
