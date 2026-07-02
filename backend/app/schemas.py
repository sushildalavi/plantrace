from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FingerprintOut(ORMBase):
    id: UUID
    fingerprint_hash: str
    normalized_query: str
    first_seen_at: datetime
    last_seen_at: datetime


class MetricPoint(ORMBase):
    captured_at: datetime
    calls: int
    total_exec_time_ms: float
    mean_exec_time_ms: float
    rows_returned: int
    shared_blks_hit: int
    shared_blks_read: int
    temp_blks_written: int


class PlanSummary(ORMBase):
    id: UUID
    captured_at: datetime
    top_node_type: str | None
    uses_seq_scan: bool
    uses_index_scan: bool
    estimated_total_cost: float | None
    actual_rows: int | None
    estimated_rows: int | None


class PlanDetail(PlanSummary):
    plan_json: list[dict[str, Any]] | dict[str, Any]
    planning_time_ms: float | None
    execution_time_ms: float | None


class DiagnosticOut(ORMBase):
    id: UUID
    fingerprint_id: UUID
    plan_id: UUID | None
    diagnostic_type: str
    severity: str
    title: str
    explanation: str
    suggested_action: str | None
    evidence_json: dict[str, Any]
    created_at: datetime


class RegressionOut(ORMBase):
    id: UUID
    fingerprint_id: UUID
    severity: str
    regression_type: str
    message: str
    old_metric_json: dict[str, Any] | None
    new_metric_json: dict[str, Any] | None
    created_at: datetime


class RegressionListItem(RegressionOut):
    normalized_query: str


class QuerySummary(ORMBase):
    id: UUID
    fingerprint_hash: str
    normalized_query: str
    last_seen_at: datetime
    latest_mean_ms: float | None = None
    latest_calls: int | None = None
    regression_count: int = 0


class QueryDetail(ORMBase):
    fingerprint: FingerprintOut
    latest_metric: MetricPoint | None
    latest_plan: PlanSummary | None
    regression_count: int


class QueryDiagnosticsOut(ORMBase):
    fingerprint: FingerprintOut
    latest_plan: PlanSummary | None
    diagnostics: list[DiagnosticOut]
    diagnostic_count: int
    latest_metric: MetricPoint | None = None


class RecommendationOut(BaseModel):
    id: str
    title: str
    severity: str
    confidence: str
    explanation: str
    suggested_action: str
    evidence_fields: list[str]
    safe_sql: str | None = None


class RecommendationList(BaseModel):
    items: list[RecommendationOut]


class AgentTraceStep(BaseModel):
    step_name: str
    input_summary: str
    tool_name: str | None = None
    tool_args_summary: str | None = None
    output_summary: str
    latency_ms: float | None = None
    status: str
    error: str | None = None


class AgentReport(BaseModel):
    regression_summary: str
    evidence_fields: list[str]
    recommendation: RecommendationOut | None
    safe_sql: str | None
    confidence: float
    safety_warnings: list[str]
    trace: list[AgentTraceStep]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class CollectResult(BaseModel):
    fingerprints: int
    metrics: int
    plans: int
    regressions: int
    diagnostics: int
    duration_ms: float


class ReportResult(BaseModel):
    generated_text: str
    model_name: str | None
    findings: dict[str, Any]


class HealthOut(BaseModel):
    status: str
    db: str = Field(default="ok")


class CollectorStatusOut(ORMBase):
    service_id: str
    environment: str
    database_name: str
    status: str
    message: str | None
    last_seen_at: datetime


class ResourceVector(BaseModel):
    cpu: float
    memory: float
    storage: float
    iops: float
    p95_latency_ms: float


class TenantTelemetryOut(BaseModel):
    tenant_id: str
    database_name: str
    region: str
    sql_fingerprint: str
    normalized_sql: str
    calls: int
    mean_exec_time_ms: float
    p95_latency_ms: float
    cpu: float
    memory: float
    storage: float
    iops: float
    migration_cost: float


class PlacementNodeOut(BaseModel):
    node_id: str
    region: str
    cluster_id: str
    availability_zone: str
    capacity: ResourceVector
    used: ResourceVector
    overloaded: bool
    tenants: list[str]
    overload_score: float


class PlacementComparisonOut(BaseModel):
    overloaded_nodes_before: int
    overloaded_nodes_after: int
    balance_before: float
    balance_after: float
    migration_cost: float
    hotspot_reduction: float
    p95_decision_latency_ms: float


class PlacementAlgorithmOut(BaseModel):
    algorithm: str
    nodes: list[PlacementNodeOut]
    comparison: PlacementComparisonOut


class PlacementSimulationOut(BaseModel):
    seed: int
    tenants: int
    regions: int
    clusters_per_region: int
    nodes_per_cluster: int
    telemetry: list[TenantTelemetryOut]
    algorithms: list[PlacementAlgorithmOut]


class PlacementSimulationRequest(BaseModel):
    seed: int = 42
    tenants: int = 48
    regions: int = 3
    clusters_per_region: int = 2
    nodes_per_cluster: int = 3
    algorithms: list[str] | None = None
