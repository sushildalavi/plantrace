from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class InvestigationEvidenceOut(BaseModel):
    signal: str
    observed_value: str
    why_it_matters: str


class EvidenceCitation(BaseModel):
    signal: str
    source: str
    observed_value: str
    rationale: str


class ExplainDiffSummary(BaseModel):
    previous_shape: str | None = None
    current_shape: str | None = None
    plan_delta: str
    row_estimate_delta: str | None = None
    access_path_delta: str | None = None


class QueryRewriteSuggestion(BaseModel):
    title: str
    rationale: str
    sql: str | None = None


class IndexRecommendation(BaseModel):
    title: str
    rationale: str
    sql: str | None = None
    operator_class: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class QueryInvestigationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    risk_level: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    remediation_priority: Literal["p0", "p1", "p2", "p3"] = "p2"
    root_cause: str | None = None
    why_this_changed: str | None = None
    regression_timeline: str | None = None
    affected_query_fingerprint_summary: str | None = None
    explain_diff_summary: ExplainDiffSummary | None = None
    query_rewrite_suggestion: QueryRewriteSuggestion | None = None
    index_recommendation: IndexRecommendation | None = None
    evidence_citations: list[EvidenceCitation] = Field(default_factory=list)
    likely_causes: list[str] = Field(default_factory=list)
    evidence: list[InvestigationEvidenceOut] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False


class QueryInvestigationRequest(BaseModel):
    query_id: UUID | None = None
    fingerprint: UUID | None = None
    regression_id: UUID | None = None

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def _require_target(self):
        if not (self.query_id or self.fingerprint or self.regression_id):
            raise ValueError("provide query_id, fingerprint, or regression_id")
        return self


class QueryInvestigationResponse(BaseModel):
    report: QueryInvestigationOut
    provider: str
    model_name: str | None = None
    source: Literal["llm", "heuristic", "insufficient"]
    grounded: bool
    latency_ms: float
    insufficient_reason: str | None = None
