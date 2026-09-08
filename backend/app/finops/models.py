"""SQLAlchemy models for Enterprise FinOps, AI Cost Governance & Usage Optimization."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CostEvent(Base, TimestampMixin):
    """Canonical, append-only, immutable cost ledger entry for all AI and compute operations."""

    __tablename__ = "cost_events"
    __table_args__ = (
        Index("ix_cost_events_org_timestamp", "organization_id", "timestamp"),
        Index("ix_cost_events_provider_model", "provider", "model"),
        Index("ix_cost_events_operation", "operation"),
        Index("ix_cost_events_request_id", "request_id"),
        Index("ix_cost_events_pricing_ver", "pricing_version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    agent_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)  # CostOperation

    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cached_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(14, 8), default=Decimal("0.0"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    pricing_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    is_retry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_failed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class ModelPricing(Base, TimestampMixin):
    """Versioned model pricing rates per 1,000,000 tokens."""

    __tablename__ = "model_pricing"
    __table_args__ = (
        Index("ix_model_pricing_provider_model", "provider", "model"),
        Index("ix_model_pricing_effective", "effective_from", "effective_until"),
        Index("ix_model_pricing_version", "provider", "model", "version", unique=True),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    input_price_per_1m: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    output_price_per_1m: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cached_input_price_per_1m: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="CONFIGURED_ESTIMATE", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Budget(Base, TimestampMixin):
    """Tenant-scoped hierarchical budget tracking spending limits, thresholds, and states."""

    __tablename__ = "finops_budgets"
    __table_args__ = (
        Index("ix_finops_budgets_org_scope", "organization_id", "scope", "scope_id"),
        Index("ix_finops_budgets_period", "period"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope: Mapped[str] = mapped_column(
        String(32), default="ORGANIZATION", nullable=False
    )  # BudgetScope
    scope_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # project_id, user_id, etc.
    parent_budget_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    period: Mapped[str] = mapped_column(
        String(16), default="MONTHLY", nullable=False
    )  # BudgetPeriod
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)

    warning_percent: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)
    critical_percent: Mapped[float] = mapped_column(Float, default=95.0, nullable=False)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Quota(Base, TimestampMixin):
    """Resource consumption quotas for requests, tokens, or spend within a duration."""

    __tablename__ = "finops_quotas"
    __table_args__ = (Index("ix_finops_quotas_org_type", "organization_id", "quota_type"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quota_type: Mapped[str] = mapped_column(String(32), nullable=False)  # QuotaType
    scope: Mapped[str] = mapped_column(String(32), default="ORGANIZATION", nullable=False)
    scope_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    limit_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    period_seconds: Mapped[int] = mapped_column(
        Integer, default=86400, nullable=False
    )  # e.g. 3600 for hour, 86400 for day
    enforcement_mode: Mapped[str] = mapped_column(
        String(16), default="BLOCK", nullable=False
    )  # QuotaEnforcementMode
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CostPolicy(Base, TimestampMixin):
    """Governance rules restricting per-request, daily, or monthly cost and token consumption."""

    __tablename__ = "finops_cost_policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    max_cost_per_request: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_cost_per_day: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    max_tokens_per_request: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_tokens_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_llm_calls_per_run: Mapped[int | None] = mapped_column(Integer, nullable=True)
    enforcement_mode: Mapped[str] = mapped_column(
        String(16), default="BLOCK", nullable=False
    )  # CostEnforcementMode
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CostAnomaly(Base, TimestampMixin):
    """Detected spending or token surges deviating significantly from historical baselines."""

    __tablename__ = "finops_cost_anomalies"
    __table_args__ = (
        Index("ix_finops_anomalies_org_detected", "organization_id", "detected_at"),
        Index("ix_finops_anomalies_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    anomaly_type: Mapped[str] = mapped_column(String(32), nullable=False)  # AnomalyType
    severity: Mapped[str] = mapped_column(
        String(16), default="WARNING", nullable=False
    )  # FinOpsSeverity
    status: Mapped[str] = mapped_column(
        String(16), default="OPEN", nullable=False
    )  # OPEN, RESOLVED, DISMISSED

    baseline_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    deviation_percent: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_impact: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0"), nullable=False
    )

    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_entity: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )  # model name, feature, or agent
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CostForecast(Base, TimestampMixin):
    """Deterministic spend trajectories and projected period end overruns."""

    __tablename__ = "finops_cost_forecasts"
    __table_args__ = (Index("ix_finops_forecasts_org_period", "organization_id", "period"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period: Mapped[str] = mapped_column(String(16), default="MONTHLY", nullable=False)

    actual_to_date: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    forecasted_total: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    budget_limit: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    expected_overrun: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.90, nullable=False)
    forecast_method: Mapped[str] = mapped_column(
        String(32), default="WEIGHTED_MOVING_AVERAGE", nullable=False
    )


class OptimizationRecommendation(Base, TimestampMixin):
    """Evidence-backed FinOps recommendations to reduce AI spend without degrading quality."""

    __tablename__ = "finops_recommendations"
    __table_args__ = (Index("ix_finops_recommendations_status", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # RecommendationType
    status: Mapped[str] = mapped_column(
        String(16), default="OPEN", nullable=False
    )  # OPEN, APPLIED, DISMISSED

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    current_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    expected_saving: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    quality_impact: Mapped[str] = mapped_column(String(32), default="NEGLIGIBLE", nullable=False)
    latency_impact: Mapped[str] = mapped_column(String(32), default="NEUTRAL", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class CostReconciliation(Base, TimestampMixin):
    """Audit comparison runs matching gateway invocations against cost ledger records."""

    __tablename__ = "finops_reconciliations"
    __table_args__ = (Index("ix_finops_reconciliations_org_status", "organization_id", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(24), default="MATCHED", nullable=False
    )  # ReconciliationStatus
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    matched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mismatched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unknown_pricing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discrepancy_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), default=Decimal("0.0"), nullable=False
    )
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)


class CostCorrection(Base, TimestampMixin):
    """Append-only compensating adjustments to rectify billing or calculation discrepancies."""

    __tablename__ = "finops_cost_corrections"
    __table_args__ = (Index("ix_finops_corrections_original", "original_event_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    adjustment_cost: Mapped[Decimal] = mapped_column(Numeric(14, 8), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
