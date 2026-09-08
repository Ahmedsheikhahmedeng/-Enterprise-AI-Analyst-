"""Pydantic V2 schemas for SRE, SLI/SLO, Alerts, Incidents, Runbooks, and Release Gates."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.sre.enums import (
    AlertSeverityEnum,
    DependencyHealthStatusEnum,
    IncidentSeverityEnum,
    IncidentStatusEnum,
    MetricTypeEnum,
    OperationalStatusEnum,
    ReleaseGateDecisionEnum,
    SLOStatusEnum,
    SLOTypeEnum,
)

# ---------------------------------------------------------------------------
# SLI Schemas
# ---------------------------------------------------------------------------


class SLICreate(BaseModel):
    name: str = Field(..., max_length=120)
    description: str | None = None
    service: str = Field(..., max_length=100)
    metric_type: MetricTypeEnum = MetricTypeEnum.AVAILABILITY
    query_config: dict[str, Any] = Field(default_factory=dict)
    unit: str = Field(default="ratio", max_length=30)
    enabled: bool = True


class SLIUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    query_config: dict[str, Any] | None = None
    unit: str | None = None
    enabled: bool | None = None


class SLIResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    name: str
    description: str | None
    service: str
    metric_type: str
    query_config: dict[str, Any]
    unit: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SLIEvaluationResult(BaseModel):
    sli_id: uuid.UUID
    name: str
    service: str
    metric_type: str
    value: float
    unit: str
    window_seconds: int
    evaluated_at: datetime


# ---------------------------------------------------------------------------
# SLO & Error Budget & Burn Rate Schemas
# ---------------------------------------------------------------------------


class SLOCreate(BaseModel):
    sli_id: uuid.UUID
    name: str = Field(..., max_length=120)
    description: str | None = None
    service: str = Field(..., max_length=100)
    target_value: float = Field(..., ge=0.0, le=1.0)
    window_seconds: int = Field(default=86400, ge=60)
    objective_type: SLOTypeEnum = SLOTypeEnum.AVAILABILITY
    warning_threshold: float = Field(default=0.995, ge=0.0, le=1.0)
    critical_threshold: float = Field(default=0.990, ge=0.0, le=1.0)
    enabled: bool = True


class SLOUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    target_value: float | None = Field(default=None, ge=0.0, le=1.0)
    window_seconds: int | None = Field(default=None, ge=60)
    warning_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    critical_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    enabled: bool | None = None


class SLOResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    sli_id: uuid.UUID
    name: str
    description: str | None
    service: str
    target_value: float
    window_seconds: int
    objective_type: str
    warning_threshold: float
    critical_threshold: float
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ErrorBudgetResponse(BaseModel):
    slo_id: uuid.UUID
    name: str
    service: str
    target: float
    window_seconds: int
    budget_total: float
    budget_consumed: float
    budget_remaining: float
    budget_remaining_percent: float
    status: SLOStatusEnum
    calculated_at: datetime


class BurnRateWindow(BaseModel):
    window_name: str
    window_seconds: int
    actual_error_rate: float
    allowed_error_rate: float
    burn_rate: float


class BurnRateResponse(BaseModel):
    slo_id: uuid.UUID
    name: str
    service: str
    fast_burn_window: BurnRateWindow
    slow_burn_window: BurnRateWindow
    is_critical_burn: bool
    is_warning_burn: bool
    evaluated_at: datetime


class SLOEvaluationResult(BaseModel):
    slo_id: uuid.UUID
    name: str
    service: str
    target_value: float
    actual_value: float
    window_seconds: int
    status: SLOStatusEnum
    error_budget: ErrorBudgetResponse
    burn_rate: BurnRateResponse
    evaluated_at: datetime


# ---------------------------------------------------------------------------
# Alert Rules & Alerts Schemas
# ---------------------------------------------------------------------------


class AlertRuleCreate(BaseModel):
    sli_id: uuid.UUID | None = None
    slo_id: uuid.UUID | None = None
    runbook_id: uuid.UUID | None = None
    name: str = Field(..., max_length=150)
    service: str = Field(..., max_length=100)
    severity: AlertSeverityEnum = AlertSeverityEnum.WARNING
    condition_operator: str = Field(default=">", max_length=10)
    threshold: float
    duration_seconds: int = Field(default=60, ge=0)
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    severity: AlertSeverityEnum | None = None
    condition_operator: str | None = None
    threshold: float | None = None
    duration_seconds: int | None = None
    runbook_id: uuid.UUID | None = None
    enabled: bool | None = None


class AlertRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    sli_id: uuid.UUID | None
    slo_id: uuid.UUID | None
    runbook_id: uuid.UUID | None
    name: str
    service: str
    severity: str
    condition_operator: str
    threshold: float
    duration_seconds: int
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AlertIngest(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = None
    service: str = Field(..., max_length=100)
    severity: AlertSeverityEnum = AlertSeverityEnum.WARNING
    metric: str = Field(..., max_length=100)
    source: str = Field(default="sre_engine", max_length=100)
    sli_name: str | None = None
    slo_name: str | None = None
    value: float | None = None
    threshold: float | None = None
    trace_id: str | None = None
    request_id: str | None = None
    rule_id: uuid.UUID | None = None


class AlertAcknowledgeRequest(BaseModel):
    actor: str = Field(..., max_length=100)
    note: str | None = None


class AlertSuppressRequest(BaseModel):
    actor: str = Field(..., max_length=100)
    reason: str = Field(..., max_length=300)
    duration_seconds: int = Field(default=3600, ge=60)


class AlertResolveRequest(BaseModel):
    actor: str = Field(..., max_length=100)
    note: str | None = None


class AlertEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alert_id: uuid.UUID
    organization_id: uuid.UUID | None
    event_type: str
    message: str
    actor: str | None
    payload: dict[str, Any]
    created_at: datetime


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    rule_id: uuid.UUID | None
    incident_id: uuid.UUID | None
    fingerprint: str
    name: str
    description: str | None
    service: str
    severity: str
    status: str
    source: str
    metric: str
    sli_name: str | None
    slo_name: str | None
    value: float | None
    threshold: float | None
    starts_at: datetime
    ends_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    count: int
    trace_id: str | None
    request_id: str | None
    created_at: datetime
    updated_at: datetime


class AlertNoiseResponse(BaseModel):
    total_alerts: int
    duplicate_alerts: int
    unique_fingerprints: int
    noise_ratio: float
    noise_level: str  # LOW, MEDIUM, HIGH


# ---------------------------------------------------------------------------
# Incidents Schemas
# ---------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: str | None = None
    service: str = Field(..., max_length=100)
    severity: IncidentSeverityEnum = IncidentSeverityEnum.SEV3
    incident_commander_id: uuid.UUID | None = None
    primary_responder_id: uuid.UUID | None = None
    service_owner: str | None = None
    initial_alert_ids: list[uuid.UUID] = Field(default_factory=list)


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatusEnum
    actor: str = Field(..., max_length=100)
    message: str = Field(..., max_length=500)
    root_cause: str | None = None
    postmortem_url: str | None = None


class IncidentAssignRequest(BaseModel):
    actor: str = Field(..., max_length=100)
    incident_commander_id: uuid.UUID | None = None
    primary_responder_id: uuid.UUID | None = None


class IncidentNoteCreate(BaseModel):
    actor: str = Field(..., max_length=100)
    note: str = Field(..., max_length=500)
    correlation_id: str | None = None


class IncidentLinkAlertRequest(BaseModel):
    alert_id: uuid.UUID
    actor: str = Field(..., max_length=100)


class IncidentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID
    organization_id: uuid.UUID | None
    event_type: str
    actor: str | None
    message: str
    metadata_payload: dict[str, Any] = Field(alias="metadata", default_factory=dict)
    correlation_id: str | None
    created_at: datetime


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    title: str
    description: str | None
    service: str
    severity: str
    status: str
    incident_commander_id: uuid.UUID | None
    primary_responder_id: uuid.UUID | None
    service_owner: str | None
    opened_at: datetime
    acknowledged_at: datetime | None
    mitigated_at: datetime | None
    resolved_at: datetime | None
    closed_at: datetime | None
    root_cause: str | None
    postmortem_url: str | None
    created_at: datetime
    updated_at: datetime


class IncidentMetricsResponse(BaseModel):
    total_incidents: int
    open_incidents: int
    mtta_seconds: float | None  # Mean Time To Acknowledge
    mttr_seconds: float | None  # Mean Time To Resolve
    mttr_p95_seconds: float | None
    by_severity: dict[str, int]
    by_service: dict[str, int]


# ---------------------------------------------------------------------------
# Dependency Health Schemas
# ---------------------------------------------------------------------------


class DependencyHealthItem(BaseModel):
    name: str
    service: str
    status: DependencyHealthStatusEnum
    latency_ms: float
    last_success: datetime | None
    last_failure: datetime | None
    error_rate: float
    message: str | None = None


class DependencyMatrixResponse(BaseModel):
    dependencies: list[DependencyHealthItem]
    overall_status: DependencyHealthStatusEnum
    degraded_components: list[str]
    checked_at: datetime


# ---------------------------------------------------------------------------
# Runbook Schemas
# ---------------------------------------------------------------------------


class RunbookCreate(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    service: str = Field(..., max_length=100)
    trigger: str = Field(..., max_length=200)
    symptoms: list[str] = Field(default_factory=list)
    diagnostic_steps: list[str] = Field(default_factory=list)
    safe_actions: list[str] = Field(default_factory=list)
    rollback_notes: str | None = None
    owner: str = Field(default="sre-team", max_length=120)


class RunbookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger: str | None = None
    symptoms: list[str] | None = None
    diagnostic_steps: list[str] | None = None
    safe_actions: list[str] | None = None
    rollback_notes: str | None = None
    owner: str | None = None


class RunbookResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    name: str
    description: str | None
    service: str
    trigger: str
    symptoms: list[str]
    diagnostic_steps: list[str]
    safe_actions: list[str]
    rollback_notes: str | None
    owner: str
    version: int
    is_published: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Maintenance Windows Schemas
# ---------------------------------------------------------------------------


class MaintenanceWindowCreate(BaseModel):
    service: str | None = None  # None indicates whole platform
    reason: str = Field(..., max_length=300)
    starts_at: datetime
    ends_at: datetime


class MaintenanceWindowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    service: str | None
    reason: str
    starts_at: datetime
    ends_at: datetime
    created_by: uuid.UUID | None
    status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Release Safety Gate Schemas
# ---------------------------------------------------------------------------


class ReleaseGateEvaluateRequest(BaseModel):
    service: str = Field(..., max_length=100)
    evaluated_by: str | None = None
    min_budget_remaining_pct: float = Field(default=10.0, ge=0.0, le=100.0)
    max_error_rate: float = Field(default=0.05, ge=0.0, le=1.0)


class ReleaseGateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID | None
    service: str
    evaluated_by: str | None
    decision: ReleaseGateDecisionEnum
    reasons: list[str]
    error_budget_remaining_pct: float | None
    open_incidents_count: int
    recent_error_rate: float | None
    evaluated_at: datetime


# ---------------------------------------------------------------------------
# Operational Dashboards Schemas
# ---------------------------------------------------------------------------


class PlatformOverviewResponse(BaseModel):
    operational_status: OperationalStatusEnum
    availability_pct: float
    error_rate_pct: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    firing_alerts_count: int
    open_incidents_count: int
    sev1_incidents_count: int
    active_maintenance: bool
    evaluated_at: datetime


class ServiceDashboardResponse(BaseModel):
    service: str
    operational_status: OperationalStatusEnum
    slis: list[SLIEvaluationResult]
    slos: list[SLOEvaluationResult]
    firing_alerts: list[AlertResponse]
    active_incidents: list[IncidentResponse]
    dependencies: list[DependencyHealthItem]


class WorkerDashboardResponse(BaseModel):
    service: str = "workers"
    queue_depth: int
    queue_lag_seconds: float
    concurrency_active: int
    concurrency_limit: int
    success_rate: float
    failure_rate: float
    dead_letter_count: int
    heartbeat_fresh: bool


class LLMDashboardResponse(BaseModel):
    service: str = "llm_gateway"
    provider_availability: float
    average_latency_ms: float
    error_rate: float
    fallback_rate: float
    token_usage_total: int
    estimated_cost_usd: float


class StreamingDashboardResponse(BaseModel):
    service: str = "sse_streaming"
    active_connections: int
    disconnect_rate: float
    reconnect_rate: float
    stream_failures: int
    average_duration_seconds: float


class OperationalReadinessResponse(BaseModel):
    status: str  # READY, NOT_READY, DEGRADED
    reasons: list[str]
    health_endpoints_ok: bool
    dependencies_ok: bool
    slos_ok: bool
    error_budget_ok: bool
    no_critical_incidents: bool
    backup_fresh: bool
    observability_ok: bool
    checked_at: datetime
