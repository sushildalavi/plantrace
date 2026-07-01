from __future__ import annotations

import time

from fastapi import APIRouter

from app.core.placement import simulate_placement
from app.observability.metrics import placement_failures_total, placement_latency_seconds
from app.schemas import PlacementSimulationOut, PlacementSimulationRequest

router = APIRouter(prefix="/api/placement", tags=["placement"])


@router.post("/simulate", response_model=PlacementSimulationOut)
def simulate(request: PlacementSimulationRequest):
    t0 = time.perf_counter()
    try:
        result = simulate_placement(
            seed=request.seed,
            tenants=request.tenants,
            regions=request.regions,
            clusters_per_region=request.clusters_per_region,
            nodes_per_cluster=request.nodes_per_cluster,
            algorithms=request.algorithms,
        )
        elapsed = time.perf_counter() - t0
        placement_latency_seconds.labels(algorithm="all").observe(elapsed)
        return PlacementSimulationOut.model_validate(result)
    except Exception:
        placement_failures_total.inc()
        raise
