"""Pydantic V2 Schemas for Enterprise Reliability, Chaos Engineering & Production Readiness."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.reliability.enums import (
    AssertionStatus,
    AssertionType,
    FailureClassification,
    FaultType,
    InjectorLifecycle,
    ReadinessDecision,
    ReliabilityRunStatus,
    ScenarioCategory,
)


class ScenarioBase(BaseModel):
    """Base properties of a reliability scenario."""

    name: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10)
    category: ScenarioCategory
    severity: str = Field(default="SEV2", pattern=r"^SEV[1-4]$")
    enabled: bool = True
    timeout_seconds: int = Field(default=60, ge=5, le=600)
    max_duration_seconds: int = Field(default=120, ge=10, le=1200)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ScenarioCreate(ScenarioBase):
    """Payload to register a new scenario."""

    pass


class ScenarioResponse(ScenarioBase):
    """API representation of a reliability scenario."""

    id: str
    organization_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunTriggerRequest(BaseModel):
    """Payload to trigger execution of a chaos scenario."""

    scenario_id: str
    environment: str = Field(
        default="test", description="Target environment (must not be 'production')"
    )
    parameters_override: dict[str, Any] = Field(default_factory=dict)
    force: bool = Field(default=False, description="Force run even if warnings exist")


class FaultResponse(BaseModel):
    """API representation of an injected fault."""

    id: str
    run_id: str
    fault_type: FaultType
    lifecycle: InjectorLifecycle
    injected_at: datetime
    recovered_at: datetime | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssertionResponse(BaseModel):
    """API representation of a verification assertion check."""

    id: str
    run_id: str
    assertion_type: AssertionType
    status: AssertionStatus
    description: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunResponse(BaseModel):
    """Summary of a reliability scenario execution run."""

    id: str
    scenario_id: str
    organization_id: uuid.UUID | None = None
    environment: str
    status: ReliabilityRunStatus
    fault_type: FaultType
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: float | None = None

    mttd_seconds: float | None = None
    mtta_seconds: float | None = None
    mttr_seconds: float | None = None
    time_to_recovery_seconds: float | None = None

    slo_impact_pct: float = 0.0
    error_budget_consumed_pct: float = 0.0
    alerts_created_count: int = 0
    incidents_created_count: int = 0
    release_gate_verdict: str | None = None
    failure_classification: FailureClassification | None = None

    correlation_id: str | None = None
    actor_id: uuid.UUID | None = None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunDetailResponse(RunResponse):
    """Detailed run record including all faults and assertions."""

    faults: list[FaultResponse] = Field(default_factory=list)
    assertions: list[AssertionResponse] = Field(default_factory=list)


class ScorecardResponse(BaseModel):
    """Deterministic reliability scorecard across domain categories."""

    id: str
    organization_id: uuid.UUID | None = None
    period_start: datetime
    period_end: datetime

    detection_score: float = Field(..., ge=0.0, le=100.0)
    recovery_score: float = Field(..., ge=0.0, le=100.0)
    integrity_score: float = Field(..., ge=0.0, le=100.0)
    degradation_score: float = Field(..., ge=0.0, le=100.0)
    isolation_score: float = Field(..., ge=0.0, le=100.0)
    slo_score: float = Field(..., ge=0.0, le=100.0)
    composite_score: float = Field(..., ge=0.0, le=100.0)

    total_scenarios_run: int = 0
    passed_count: int = 0
    failed_count: int = 0
    metrics_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReadinessFactorDetail(BaseModel):
    """Evaluation factor contributing to production readiness."""

    name: str
    status: str  # PASS, WARN, FAIL
    score: float
    details: str


class ReadinessResponse(BaseModel):
    """High-level production readiness assessment."""

    id: str
    organization_id: uuid.UUID | None = None
    decision: ReadinessDecision
    evaluator: str
    scorecard_id: str | None = None
    composite_score: float = 0.0
    evaluation_factors: dict[str, Any] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReliabilityReportResponse(BaseModel):
    """Comprehensive executive reliability and chaos validation summary."""

    total_scenarios_defined: int
    total_runs_executed: int
    passed_runs: int
    failed_runs: int
    average_mttd_seconds: float
    average_mttr_seconds: float
    readiness_decision: ReadinessDecision
    composite_reliability_score: float
    scorecard: ScorecardResponse | None = None
    latest_readiness: ReadinessResponse | None = None
    recent_runs: list[RunResponse] = Field(default_factory=list)
