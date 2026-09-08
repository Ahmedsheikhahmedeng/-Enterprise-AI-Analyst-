"""SQLAlchemy ORM Models for Enterprise Production Readiness & Chaos Engineering."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ReliabilityScenario(Base):
    """Catalog of deterministic reliability and chaos engineering scenarios."""

    __tablename__ = "reliability_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="SEV2")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    max_duration_seconds: Mapped[int] = mapped_column(Integer, default=120, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    runs: Mapped[list["ReliabilityRun"]] = relationship(
        "ReliabilityRun", back_populates="scenario", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_reliability_scenarios_org_cat", "organization_id", "category"),)


class ReliabilityRun(Base):
    """Historical record of a chaos scenario execution."""

    __tablename__ = "reliability_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    scenario_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reliability_scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    environment: Mapped[str] = mapped_column(String(50), default="test", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    fault_type: Mapped[str] = mapped_column(String(50), nullable=False)

    mttd_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    mtta_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    mttr_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_recovery_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    slo_impact_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    error_budget_consumed_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    alerts_created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    incidents_created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    release_gate_verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    failure_classification: Mapped[str | None] = mapped_column(String(50), nullable=True)

    correlation_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    scenario: Mapped["ReliabilityScenario"] = relationship(
        "ReliabilityScenario", back_populates="runs"
    )
    faults: Mapped[list["ReliabilityFault"]] = relationship(
        "ReliabilityFault", back_populates="run", cascade="all, delete-orphan"
    )
    assertions: Mapped[list["ReliabilityAssertion"]] = relationship(
        "ReliabilityAssertion", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_reliability_runs_org_status", "organization_id", "status"),
        Index("ix_reliability_runs_created_at", "created_at"),
    )


class ReliabilityFault(Base):
    """Specific fault injected during a reliability run."""

    __tablename__ = "reliability_faults"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reliability_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fault_type: Mapped[str] = mapped_column(String(50), nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(30), default="IDLE", nullable=False)
    injected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    run: Mapped["ReliabilityRun"] = relationship("ReliabilityRun", back_populates="faults")


class ReliabilityAssertion(Base):
    """Verification check evaluated during or after a chaos scenario."""

    __tablename__ = "reliability_assertions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("reliability_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assertion_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    run: Mapped["ReliabilityRun"] = relationship("ReliabilityRun", back_populates="assertions")


class ReliabilityScorecard(Base):
    """Aggregated deterministic reliability score based on executed scenarios."""

    __tablename__ = "reliability_scorecards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    detection_score: Mapped[float] = mapped_column(Float, nullable=False)
    recovery_score: Mapped[float] = mapped_column(Float, nullable=False)
    integrity_score: Mapped[float] = mapped_column(Float, nullable=False)
    degradation_score: Mapped[float] = mapped_column(Float, nullable=False)
    isolation_score: Mapped[float] = mapped_column(Float, nullable=False)
    slo_score: Mapped[float] = mapped_column(Float, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False)

    total_scenarios_run: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metrics_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class ProductionReadinessRecord(Base):
    """Evaluated Production Readiness decision with factors and blocking reasons."""

    __tablename__ = "production_readiness_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    evaluator: Mapped[str] = mapped_column(String(100), default="automated", nullable=False)
    scorecard_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    evaluation_factors: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    blockers: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
