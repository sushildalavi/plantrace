from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from statistics import pstdev
from time import perf_counter
from typing import Any

from app.core.fingerprint import fingerprint as fingerprint_sql


@dataclass(frozen=True)
class ResourceVector:
    cpu: float
    memory: float
    storage: float
    iops: float
    p95_latency_ms: float

    def scaled(self, factor: float) -> ResourceVector:
        return ResourceVector(
            cpu=self.cpu * factor,
            memory=self.memory * factor,
            storage=self.storage * factor,
            iops=self.iops * factor,
            p95_latency_ms=self.p95_latency_ms * factor,
        )

    def __add__(self, other: ResourceVector) -> ResourceVector:
        return ResourceVector(
            cpu=self.cpu + other.cpu,
            memory=self.memory + other.memory,
            storage=self.storage + other.storage,
            iops=self.iops + other.iops,
            p95_latency_ms=max(self.p95_latency_ms, other.p95_latency_ms),
        )


@dataclass(frozen=True)
class TenantWorkload:
    tenant_id: str
    database_name: str
    region_preference: str
    zone_affinity: str | None
    normalized_sql: str
    sql_fingerprint: str
    calls: int
    mean_exec_time_ms: float
    p95_latency_ms: float
    resources: ResourceVector
    migration_cost: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "database_name": self.database_name,
            "region": self.region_preference,
            "sql_fingerprint": self.sql_fingerprint,
            "normalized_sql": self.normalized_sql,
            "calls": self.calls,
            "mean_exec_time_ms": self.mean_exec_time_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "cpu": self.resources.cpu,
            "memory": self.resources.memory,
            "storage": self.resources.storage,
            "iops": self.resources.iops,
            "migration_cost": self.migration_cost,
        }


@dataclass
class NodeCapacity:
    node_id: str
    region: str
    cluster_id: str
    availability_zone: str
    capacity: ResourceVector
    used: ResourceVector = field(default_factory=lambda: ResourceVector(0, 0, 0, 0, 0))
    tenants: list[TenantWorkload] = field(default_factory=list)

    def can_host(self, tenant: TenantWorkload) -> bool:
        if tenant.region_preference and tenant.region_preference != self.region:
            return False
        if tenant.zone_affinity and tenant.zone_affinity != self.availability_zone:
            return False
        next_used = self.used + tenant.resources
        return (
            next_used.cpu <= self.capacity.cpu
            and next_used.memory <= self.capacity.memory
            and next_used.storage <= self.capacity.storage
            and next_used.iops <= self.capacity.iops
        )

    def add(self, tenant: TenantWorkload) -> None:
        self.tenants.append(tenant)
        self.used = self.used + tenant.resources

    @property
    def overload_score(self) -> float:
        ratios = [
            self.used.cpu / max(self.capacity.cpu, 1e-9),
            self.used.memory / max(self.capacity.memory, 1e-9),
            self.used.storage / max(self.capacity.storage, 1e-9),
            self.used.iops / max(self.capacity.iops, 1e-9),
        ]
        return sum(max(0.0, r - 1.0) for r in ratios)

    @property
    def overloaded(self) -> bool:
        return self.overload_score > 0

    @property
    def utilization(self) -> float:
        return max(
            self.used.cpu / max(self.capacity.cpu, 1e-9),
            self.used.memory / max(self.capacity.memory, 1e-9),
            self.used.storage / max(self.capacity.storage, 1e-9),
            self.used.iops / max(self.capacity.iops, 1e-9),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "region": self.region,
            "cluster_id": self.cluster_id,
            "availability_zone": self.availability_zone,
            "capacity": asdict(self.capacity),
            "used": asdict(self.used),
            "overloaded": self.overloaded,
            "tenants": [tenant.tenant_id for tenant in self.tenants],
            "overload_score": round(self.overload_score, 4),
        }


@dataclass
class PlacementScenario:
    seed: int
    regions: list[str]
    nodes: list[NodeCapacity]
    tenants: list[TenantWorkload]

    def clone(self) -> PlacementScenario:
        return PlacementScenario(
            seed=self.seed,
            regions=list(self.regions),
            nodes=[
                NodeCapacity(
                    node_id=node.node_id,
                    region=node.region,
                    cluster_id=node.cluster_id,
                    availability_zone=node.availability_zone,
                    capacity=node.capacity,
                )
                for node in self.nodes
            ],
            tenants=list(self.tenants),
        )


@dataclass(frozen=True)
class PlacementComparison:
    overloaded_nodes_before: int
    overloaded_nodes_after: int
    balance_before: float
    balance_after: float
    migration_cost: float
    hotspot_reduction: float
    p95_decision_latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlacementResult:
    algorithm: str
    nodes: list[NodeCapacity]
    comparison: PlacementComparison
    decision_latencies_ms: list[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "nodes": [node.to_dict() for node in self.nodes],
            "comparison": self.comparison.to_dict(),
        }


def _balance(nodes: list[NodeCapacity]) -> float:
    if len(nodes) < 2:
        return 0.0
    utilizations = [node.utilization for node in nodes]
    return round(pstdev(utilizations), 6)


def _overloaded_count(nodes: list[NodeCapacity]) -> int:
    return sum(1 for node in nodes if node.overloaded)


def _hotspot(nodes: list[NodeCapacity]) -> float:
    return round(sum(node.overload_score for node in nodes), 6)


def _decision_latency_p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(0.95 * (len(ordered) - 1)))))
    return round(ordered[idx], 4)


def _score_node(node: NodeCapacity, tenant: TenantWorkload, *, weights: dict[str, float]) -> float:
    projected = node.used + tenant.resources
    ratios = {
        "cpu": projected.cpu / max(node.capacity.cpu, 1e-9),
        "memory": projected.memory / max(node.capacity.memory, 1e-9),
        "storage": projected.storage / max(node.capacity.storage, 1e-9),
        "iops": projected.iops / max(node.capacity.iops, 1e-9),
        "latency": max(projected.p95_latency_ms, tenant.p95_latency_ms) / max(tenant.p95_latency_ms, 1e-9),
    }
    base = (
        ratios["cpu"] * weights["cpu"]
        + ratios["memory"] * weights["memory"]
        + ratios["storage"] * weights["storage"]
        + ratios["iops"] * weights["iops"]
        + ratios["latency"] * weights["latency"]
    )
    overload = sum(max(0.0, ratios[k] - 1.0) * weights[k] * 5.0 for k in ("cpu", "memory", "storage", "iops"))
    return base + overload


def _choose_node(
    scenario: PlacementScenario,
    tenant: TenantWorkload,
    *,
    selector: Callable[[list[NodeCapacity], TenantWorkload], NodeCapacity | None],
) -> NodeCapacity | None:
    feasible = [node for node in scenario.nodes if node.can_host(tenant)]
    if feasible:
        return selector(feasible, tenant)
    same_region = [node for node in scenario.nodes if node.region == tenant.region_preference]
    if same_region:
        return selector(same_region, tenant)
    return selector(scenario.nodes, tenant)


def _first_fit_selector(nodes: list[NodeCapacity], _: TenantWorkload) -> NodeCapacity | None:
    return nodes[0] if nodes else None


def _best_fit_selector(nodes: list[NodeCapacity], tenant: TenantWorkload) -> NodeCapacity | None:
    if not nodes:
        return None
    return min(nodes, key=lambda node: _score_node(node, tenant, weights={"cpu": 2.0, "memory": 2.0, "storage": 1.0, "iops": 1.5, "latency": 0.5}))


def _weighted_selector(nodes: list[NodeCapacity], tenant: TenantWorkload) -> NodeCapacity | None:
    if not nodes:
        return None
    return min(
        nodes,
        key=lambda node: _score_node(
            node,
            tenant,
            weights={"cpu": 2.5, "memory": 2.0, "storage": 1.0, "iops": 2.0, "latency": 1.5},
        ),
    )


def _assign(scenario: PlacementScenario, selector: Callable[[list[NodeCapacity], TenantWorkload], NodeCapacity | None]) -> list[float]:
    decision_latencies: list[float] = []
    for tenant in scenario.tenants:
        t0 = perf_counter()
        node = _choose_node(scenario, tenant, selector=selector)
        if node is None:
            node = min(scenario.nodes, key=lambda candidate: _score_node(candidate, tenant, weights={"cpu": 3.0, "memory": 3.0, "storage": 1.0, "iops": 2.0, "latency": 1.0}))
        node.add(tenant)
        decision_latencies.append((perf_counter() - t0) * 1000.0)
    return decision_latencies


def _tenant_map(nodes: list[NodeCapacity]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for node in nodes:
        for tenant in node.tenants:
            mapping[tenant.tenant_id] = node.node_id
    return mapping


def _compare(
    before: list[NodeCapacity],
    after: list[NodeCapacity],
    decision_latencies: list[float],
    *,
    before_map: dict[str, str],
    after_map: dict[str, str],
) -> PlacementComparison:
    before_hotspot = _hotspot(before)
    after_hotspot = _hotspot(after)
    moved_cost = 0.0
    tenant_index = {tenant.tenant_id: tenant for node in after for tenant in node.tenants}
    for tenant_id, before_node in before_map.items():
        if after_map.get(tenant_id) != before_node:
            moved_cost += tenant_index[tenant_id].migration_cost
    return PlacementComparison(
        overloaded_nodes_before=_overloaded_count(before),
        overloaded_nodes_after=_overloaded_count(after),
        balance_before=_balance(before),
        balance_after=_balance(after),
        migration_cost=round(moved_cost, 4),
        hotspot_reduction=round(before_hotspot - after_hotspot, 6),
        p95_decision_latency_ms=_decision_latency_p95(decision_latencies),
    )


def run_algorithm(scenario: PlacementScenario, algorithm: str) -> PlacementResult:
    working = scenario.clone()
    baseline = scenario.clone()
    _assign(baseline, _first_fit_selector)

    selector_map: dict[str, Callable[[list[NodeCapacity], TenantWorkload], NodeCapacity | None]] = {
        "first-fit": _first_fit_selector,
        "greedy-best-fit": _best_fit_selector,
        "weighted-scoring": _weighted_selector,
        "local-search-rebalancer": _weighted_selector,
    }
    selector = selector_map[algorithm]
    decision_latencies = _assign(working, selector)

    if algorithm == "local-search-rebalancer":
        _local_search(working)

    comparison = _compare(
        baseline.nodes,
        working.nodes,
        decision_latencies,
        before_map=_tenant_map(baseline.nodes),
        after_map=_tenant_map(working.nodes),
    )
    return PlacementResult(algorithm=algorithm, nodes=working.nodes, comparison=comparison, decision_latencies_ms=decision_latencies)


def _local_search(scenario: PlacementScenario) -> None:
    if len(scenario.nodes) < 2:
        return
    improved = True
    while improved:
        improved = False
        hotspot_nodes = sorted(scenario.nodes, key=lambda node: node.overload_score, reverse=True)
        source = hotspot_nodes[0]
        if source.overload_score <= 0:
            break
        for tenant in list(source.tenants):
            candidate_nodes = [node for node in scenario.nodes if node is not source and node.can_host(tenant)]
            if not candidate_nodes:
                continue
            target = min(candidate_nodes, key=lambda node: _score_node(node, tenant, weights={"cpu": 3.0, "memory": 3.0, "storage": 1.0, "iops": 2.0, "latency": 1.0}))
            current_score = source.overload_score + target.overload_score
            projected_source = NodeCapacity(
                node_id=source.node_id,
                region=source.region,
                cluster_id=source.cluster_id,
                availability_zone=source.availability_zone,
                capacity=source.capacity,
                used=ResourceVector(
                    cpu=source.used.cpu - tenant.resources.cpu,
                    memory=source.used.memory - tenant.resources.memory,
                    storage=source.used.storage - tenant.resources.storage,
                    iops=source.used.iops - tenant.resources.iops,
                    p95_latency_ms=source.used.p95_latency_ms,
                ),
                tenants=[t for t in source.tenants if t.tenant_id != tenant.tenant_id],
            )
            projected_target = NodeCapacity(
                node_id=target.node_id,
                region=target.region,
                cluster_id=target.cluster_id,
                availability_zone=target.availability_zone,
                capacity=target.capacity,
                used=target.used + tenant.resources,
                tenants=target.tenants + [tenant],
            )
            projected_score = projected_source.overload_score + projected_target.overload_score
            if projected_score + 1e-6 < current_score:
                source.tenants = [t for t in source.tenants if t.tenant_id != tenant.tenant_id]
                source.used = projected_source.used
                target.add(tenant)
                improved = True
                break


def generate_synthetic_telemetry(*, seed: int, tenants: int) -> list[TenantWorkload]:
    import random

    rng = random.Random(seed)
    regions = ["eastus", "westus", "centralus"]
    zones = ["1", "2", "3"]
    sql_templates = [
        "select * from invoices where tenant_id = {tenant_id} and status = 'open'",
        "select count(*) from events where tenant_id = {tenant_id} and created_at > now() - interval '7 days'",
        "select user_id, count(*) from clicks where tenant_id = {tenant_id} group by user_id order by count(*) desc limit 20",
        "select avg(latency_ms) from request_logs where tenant_id = {tenant_id} and region = '{region}'",
        "select * from search_results where tenant_id = {tenant_id} order by embedding <-> '[0.1,0.2,0.3,0.4]' limit 10",
    ]
    out: list[TenantWorkload] = []
    for idx in range(tenants):
        region = rng.choice(regions)
        zone = rng.choice(zones)
        calls = rng.randint(100, 20_000)
        mean_ms = round(rng.uniform(3.0, 180.0), 2)
        p95 = round(mean_ms * rng.uniform(1.3, 3.8), 2)
        cpu = round(rng.uniform(0.3, 6.5), 2)
        memory = round(rng.uniform(1.0, 24.0), 2)
        storage = round(rng.uniform(10.0, 160.0), 2)
        iops = round(rng.uniform(50.0, 1600.0), 2)
        migration_cost = round(cpu * 8 + memory * 1.5 + storage * 0.06 + iops * 0.01, 2)
        sql = rng.choice(sql_templates).format(tenant_id=idx + 1, region=region)
        normalized_sql, sql_fingerprint = fingerprint_sql(sql)
        out.append(
            TenantWorkload(
                tenant_id=f"tenant-{idx + 1:03d}",
                database_name=f"tenant_db_{idx + 1:03d}",
                region_preference=region,
                zone_affinity=zone if rng.random() < 0.45 else None,
                normalized_sql=normalized_sql,
                sql_fingerprint=sql_fingerprint,
                calls=calls,
                mean_exec_time_ms=mean_ms,
                p95_latency_ms=p95,
                resources=ResourceVector(
                    cpu=cpu,
                    memory=memory,
                    storage=storage,
                    iops=iops,
                    p95_latency_ms=p95,
                ),
                migration_cost=migration_cost,
            )
        )
    return out


def build_scenario(*, seed: int, tenants: int, regions: int, clusters_per_region: int, nodes_per_cluster: int) -> PlacementScenario:
    import random

    rng = random.Random(seed)
    region_names = ["eastus", "westus", "centralus", "northcentralus", "southcentralus"][:regions]
    telemetry = generate_synthetic_telemetry(seed=seed, tenants=tenants)
    nodes: list[NodeCapacity] = []
    node_idx = 1
    for region in region_names:
        for cluster_idx in range(clusters_per_region):
            cluster_id = f"{region}-cluster-{cluster_idx + 1}"
            for _ in range(nodes_per_cluster):
                capacity = ResourceVector(
                    cpu=round(rng.uniform(24, 64), 2),
                    memory=round(rng.uniform(96, 256), 2),
                    storage=round(rng.uniform(500, 2_000), 2),
                    iops=round(rng.uniform(4_000, 18_000), 2),
                    p95_latency_ms=round(rng.uniform(20, 80), 2),
                )
                nodes.append(
                    NodeCapacity(
                        node_id=f"node-{node_idx:03d}",
                        region=region,
                        cluster_id=cluster_id,
                        availability_zone=str((node_idx % 3) + 1),
                        capacity=capacity,
                    )
                )
                node_idx += 1
    return PlacementScenario(seed=seed, regions=region_names, nodes=nodes, tenants=telemetry)


def simulate_placement(
    *,
    seed: int,
    tenants: int,
    regions: int,
    clusters_per_region: int,
    nodes_per_cluster: int,
    algorithms: list[str] | None = None,
) -> dict[str, Any]:
    scenario = build_scenario(
        seed=seed,
        tenants=tenants,
        regions=regions,
        clusters_per_region=clusters_per_region,
        nodes_per_cluster=nodes_per_cluster,
    )
    algorithms = algorithms or ["first-fit", "greedy-best-fit", "weighted-scoring", "local-search-rebalancer"]
    results = [run_algorithm(scenario, algorithm) for algorithm in algorithms]
    return {
        "seed": seed,
        "tenants": tenants,
        "regions": len(scenario.regions),
        "clusters_per_region": clusters_per_region,
        "nodes_per_cluster": nodes_per_cluster,
        "telemetry": [tenant.to_dict() for tenant in scenario.tenants],
        "algorithms": [result.to_dict() for result in results],
    }
