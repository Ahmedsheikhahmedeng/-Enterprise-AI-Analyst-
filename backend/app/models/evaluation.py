"""SQLAlchemy 2 database models for Enterprise AI Evaluation & Quality Framework."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class EvaluationDataset(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantScopedMixin):
    """Collection of evaluation test cases representing domain benchmark suites."""

    __tablename__ = "evaluation_datasets"
    __table_args__ = (
        Index("ix_evaluation_datasets_org_status", "organization_id", "status"),
        Index("ix_evaluation_datasets_org_name", "organization_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    versions: Mapped[list["EvaluationDatasetVersion"]] = relationship(
        "EvaluationDatasetVersion",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="EvaluationDatasetVersion.version_number.desc()",
    )
    cases: Mapped[list["EvaluationCase"]] = relationship(
        "EvaluationCase",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )
    runs: Mapped[list["EvaluationRun"]] = relationship(
        "EvaluationRun",
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class EvaluationDatasetVersion(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Immutable snapshot of an evaluation dataset version."""

    __tablename__ = "evaluation_dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number", name="uq_eval_dataset_version"),
        Index("ix_evaluation_dataset_versions_org_id", "organization_id"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cases_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    dataset: Mapped["EvaluationDataset"] = relationship(
        "EvaluationDataset",
        back_populates="versions",
    )


class EvaluationCase(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Specific query and ground-truth expectations for benchmark evaluation."""

    __tablename__ = "evaluation_cases"
    __table_args__ = (
        Index("ix_evaluation_cases_dataset_route", "dataset_id", "route_expected"),
        Index("ix_evaluation_cases_org_id", "organization_id"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    route_expected: Mapped[str] = mapped_column(String(50), nullable=False)
    datasource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_citations: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    expected_documents: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    expected_sql_semantics: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    expected_rows: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    relevant_chunks: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    tags: Mapped[list[Any]] = mapped_column(JSONB, default=list, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    dataset: Mapped["EvaluationDataset"] = relationship(
        "EvaluationDataset",
        back_populates="cases",
    )
    results: Mapped[list["EvaluationCaseResult"]] = relationship(
        "EvaluationCaseResult",
        back_populates="case",
        cascade="all, delete-orphan",
    )


class EvaluationRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Execution run of an evaluation benchmark against a dataset version."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        Index("ix_evaluation_runs_dataset_status", "dataset_id", "status"),
        Index("ix_evaluation_runs_org_created", "organization_id", "created_at"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_cases: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_config_: Mapped[dict[str, Any]] = mapped_column(
        "model_config",
        JSONB,
        default=dict,
        nullable=False,
    )
    system_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    git_commit: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    dataset: Mapped["EvaluationDataset"] = relationship(
        "EvaluationDataset",
        back_populates="runs",
    )
    case_results: Mapped[list["EvaluationCaseResult"]] = relationship(
        "EvaluationCaseResult",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class EvaluationCaseResult(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Scored outcome of a single evaluation case in a benchmark run."""

    __tablename__ = "evaluation_case_results"
    __table_args__ = (
        Index("ix_evaluation_case_results_run_passed", "run_id", "passed"),
        Index("ix_evaluation_case_results_org_id", "organization_id"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evaluation_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actual_route: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expected_route: Mapped[str | None] = mapped_column(String(50), nullable=True)
    actual_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rag_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sql_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    grounding_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    citation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hallucination_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metrics_detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    run: Mapped["EvaluationRun"] = relationship(
        "EvaluationRun",
        back_populates="case_results",
    )
    case: Mapped["EvaluationCase"] = relationship(
        "EvaluationCase",
        back_populates="results",
    )
