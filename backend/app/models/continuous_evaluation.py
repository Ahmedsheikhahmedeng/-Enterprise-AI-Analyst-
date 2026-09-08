"""SQLAlchemy models for Enterprise Continuous AI Evaluation, Benchmarking & Quality Monitoring."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class BenchmarkModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Versioned benchmark definition grouping specific datasets and target architectures."""

    __tablename__ = "benchmarks"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", "version", name="uq_benchmarks_org_name_version"
        ),
        Index("ix_benchmarks_org_status", "organization_id", "status"),
        Index("ix_benchmarks_org_target", "organization_id", "target"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. RAG, SQL, AGENT
    target: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. RAG, SQL, END_TO_END
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    baseline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)


class EvaluationSuiteModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Unified collection of benchmarks testing holistic enterprise capabilities."""

    __tablename__ = "evaluation_suites"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "name", "version", name="uq_eval_suites_org_name_version"
        ),
        Index("ix_eval_suites_org_status", "organization_id", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    benchmark_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)


class QualityGateModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Configurable quality threshold policy for gating releases."""

    __tablename__ = "quality_gates"
    __table_args__ = (Index("ix_quality_gates_org_status", "organization_id", "status"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)


class QualityGateResultModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Outcome of evaluating a quality gate against an evaluation run."""

    __tablename__ = "quality_gate_results"
    __table_args__ = (Index("ix_qg_results_org_gate_run", "organization_id", "gate_id", "run_id"),)

    gate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("quality_gates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # PASS, WARN, FAIL, BLOCK_RELEASE
    scorecard: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    violations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class RegressionModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Discovered performance or accuracy regression between a run and its baseline."""

    __tablename__ = "regressions"
    __table_args__ = (
        Index("ix_regressions_org_run", "organization_id", "run_id"),
        Index("ix_regressions_org_severity", "organization_id", "severity"),
    )

    benchmark_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("benchmarks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    baseline_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # INFO, WARNING, MAJOR, CRITICAL
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    drop_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class CalibrationResultModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Confidence calibration analytics (Expected Calibration Error, Brier Score, and bucket histograms)."""

    __tablename__ = "calibration_results"
    __table_args__ = (Index("ix_calibration_results_org_run", "organization_id", "run_id"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ece: Mapped[float] = mapped_column(Float, nullable=False)
    brier_score: Mapped[float] = mapped_column(Float, nullable=False)
    reliability_buckets: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ProductionEvaluationSampleModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Sampled execution from production workloads with privacy sanitization and retention limits."""

    __tablename__ = "production_evaluation_samples"
    __table_args__ = (
        Index("ix_prod_eval_samples_org_strategy", "organization_id", "sampling_strategy"),
        Index("ix_prod_eval_samples_expires", "expires_at"),
    )

    source_execution_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)
    sampling_strategy: Mapped[str] = mapped_column(String(50), nullable=False)
    data_sensitivity: Mapped[str] = mapped_column(String(50), default="INTERNAL", nullable=False)
    redacted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class HumanEvaluationModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Human evaluator annotations and qualitative scores."""

    __tablename__ = "human_evaluations"
    __table_args__ = (Index("ix_human_eval_org_evaluator", "organization_id", "evaluator_id"),)

    sample_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("production_evaluation_samples.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    case_result_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_case_results.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    evaluator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    accuracy_score: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 to 5.0
    helpfulness_score: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 to 5.0
    grounding_score: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 to 5.0
    clarity_score: Mapped[float] = mapped_column(Float, nullable=False)  # 1.0 to 5.0
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
