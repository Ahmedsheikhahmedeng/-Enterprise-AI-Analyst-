"""Pydantic V2 schemas for Enterprise FinOps REST API endpoints."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.finops.enums import (
    BudgetPeriod,
    BudgetScope,
    BudgetState,
    CostEnforcementMode,
    CostOperation,
    FinOpsReadinessDecision,
    QuotaEnforcementMode,
    QuotaType,
)


class CostEventCreate(BaseModel):
    provider: str
    model: str
    operation: CostOperation
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_tokens: int = Field(default=0, ge=0)
    request_id: str | None = None
    trace_id: str | None = None
    agent_session_id: str | None = None
    job_id: str | None = None
    is_retry: bool = False
    is_failed: bool = False
    metadata_payload: dict[str, Any] = Field(default_factory=dict)


class CostEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    request_id: str | None = None
    trace_id: str | None = None
    agent_session_id: str | None = None
    job_id: str | None = None
    provider: str
    model: str
    operation: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    currency: str
    pricing_version: int
    timestamp: datetime
    is_retry: bool
    is_failed: bool
    metadata_payload: dict[str, Any] = Field(default_factory=dict)


class ModelPricingCreate(BaseModel):
    provider: str
    model: str
    input_price_per_1m: Decimal = Field(ge=0)
    output_price_per_1m: Decimal = Field(ge=0)
    cached_input_price_per_1m: Decimal | None = Field(default=None, ge=0)
    currency: str = "USD"
    effective_from: datetime
    effective_until: datetime | None = None
    source: str = "CONFIGURED_ESTIMATE"


class ModelPricingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    model: str
    version: int
    input_price_per_1m: Decimal
    output_price_per_1m: Decimal
    cached_input_price_per_1m: Decimal | None = None
    currency: str
    effective_from: datetime
    effective_until: datetime | None = None
    source: str
    is_active: bool


class BudgetCreate(BaseModel):
    scope: BudgetScope = BudgetScope.ORGANIZATION
    scope_id: str | None = None
    parent_budget_id: str | None = None
    period: BudgetPeriod = BudgetPeriod.MONTHLY
    limit_amount: Decimal = Field(gt=0)
    currency: str = "USD"
    warning_percent: float = Field(default=80.0, ge=0.0, le=100.0)
    critical_percent: float = Field(default=95.0, ge=0.0, le=100.0)
    starts_at: datetime
    ends_at: datetime | None = None


class BudgetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    scope: str
    scope_id: str | None = None
    parent_budget_id: str | None = None
    period: str
    limit_amount: Decimal
    currency: str
    warning_percent: float
    critical_percent: float
    enabled: bool
    starts_at: datetime
    ends_at: datetime | None = None
    created_by: str | None = None

    # Computed fields
    spent_amount: Decimal = Decimal("0.0")
    remaining_amount: Decimal = Decimal("0.0")
    utilization_percent: float = 0.0
    state: BudgetState = BudgetState.SPENDING


class QuotaCreate(BaseModel):
    quota_type: QuotaType
    scope: str = "ORGANIZATION"
    scope_id: str | None = None
    limit_value: Decimal = Field(gt=0)
    period_seconds: int = Field(default=86400, gt=0)
    enforcement_mode: QuotaEnforcementMode = QuotaEnforcementMode.BLOCK


class QuotaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    quota_type: str
    scope: str
    scope_id: str | None = None
    limit_value: Decimal
    period_seconds: int
    enforcement_mode: str
    enabled: bool
    current_usage: Decimal = Decimal("0.0")
    is_exceeded: bool = False


class CostPolicyCreate(BaseModel):
    name: str
    max_cost_per_request: Decimal | None = None
    max_cost_per_day: Decimal | None = None
    max_tokens_per_request: int | None = None
    max_tokens_per_day: int | None = None
    max_llm_calls_per_run: int | None = None
    enforcement_mode: CostEnforcementMode = CostEnforcementMode.BLOCK


class CostPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    name: str
    max_cost_per_request: Decimal | None = None
    max_cost_per_day: Decimal | None = None
    max_tokens_per_request: int | None = None
    max_tokens_per_day: int | None = None
    max_llm_calls_per_run: int | None = None
    enforcement_mode: str
    enabled: bool


class CostAnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    anomaly_type: str
    severity: str
    status: str
    baseline_amount: Decimal
    actual_amount: Decimal
    deviation_percent: float
    estimated_impact: Decimal
    description: str
    affected_entity: str | None = None
    detected_at: datetime
    resolved_at: datetime | None = None


class CostForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    period: str
    actual_to_date: Decimal
    forecasted_total: Decimal
    budget_limit: Decimal
    expected_overrun: Decimal
    confidence: float
    forecast_method: str
    created_at: datetime


class OptimizationRecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    recommendation_type: str
    status: str
    title: str
    description: str
    current_cost: Decimal
    expected_saving: Decimal
    quality_impact: str
    latency_impact: str
    confidence: float
    evidence: dict[str, Any] = Field(default_factory=dict)


class CostReconciliationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID | None = None
    status: str
    period_start: datetime
    period_end: datetime
    matched_count: int
    missing_count: int
    duplicated_count: int
    mismatched_count: int
    unknown_pricing_count: int
    discrepancy_amount: Decimal
    details: dict[str, Any] = Field(default_factory=dict)


class CostCorrectionCreate(BaseModel):
    original_event_id: str
    adjustment_cost: Decimal
    reason: str


class CostCorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: uuid.UUID
    original_event_id: str
    adjustment_cost: Decimal
    reason: str
    actor: str
    corrected_at: datetime


class AttributionBreakdownItem(BaseModel):
    dimension_key: str
    dimension_value: str
    total_cost: Decimal
    total_tokens: int
    request_count: int
    avg_cost_per_request: Decimal


class FinOpsOverviewResponse(BaseModel):
    current_spend: Decimal
    forecasted_spend: Decimal
    active_budget_limit: Decimal
    budget_remaining: Decimal
    budget_utilization_percent: float
    budget_state: BudgetState
    open_anomalies_count: int
    potential_savings_amount: Decimal
    attribution_completeness_percent: float
    wasted_cost_total: Decimal
    currency: str = "USD"
    disclaimer: str


class FinOpsReadinessResponse(BaseModel):
    decision: FinOpsReadinessDecision
    score: float
    pricing_coverage_percent: float
    attribution_completeness_percent: float
    reconciliation_matched_percent: float
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evaluated_at: datetime
