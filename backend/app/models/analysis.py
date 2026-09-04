import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
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

from app.models.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.organization import Organization
    from app.models.report import Report
    from app.models.user import User


class AnalysisRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Execution context for an autonomous multi-step reasoning and data analysis task."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_org_status", "organization_id", "status"),
        Index("ix_analysis_runs_org_created_at", "organization_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="analysis_runs",
    )
    user: Mapped["User"] = relationship("User")
    conversation: Mapped["Conversation | None"] = relationship("Conversation")
    steps: Mapped[list["AnalysisStep"]] = relationship(
        "AnalysisStep",
        back_populates="analysis_run",
        cascade="all, delete-orphan",
        order_by="AnalysisStep.step_order",
    )
    reports: Mapped[list["Report"]] = relationship(
        "Report",
        back_populates="analysis_run",
    )


class AnalysisStep(Base, UUIDPrimaryKeyMixin):
    """Granular execution step (Router, Planner, RAG, SQL, Code, Verification)."""

    __tablename__ = "analysis_steps"
    __table_args__ = (
        UniqueConstraint("analysis_run_id", "step_order", name="uq_analysis_steps_run_order"),
        Index("ix_analysis_steps_run_order", "analysis_run_id", "step_order"),
    )

    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        nullable=False,
    )
    input_payload: Mapped[dict[str, Any] | None] = mapped_column(
        "input",
        JSONB,
        nullable=True,
    )
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(
        "output",
        JSONB,
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    analysis_run: Mapped["AnalysisRun"] = relationship(
        "AnalysisRun",
        back_populates="steps",
    )
