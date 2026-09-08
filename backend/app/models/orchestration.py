"""SQLAlchemy models for Enterprise AI Response & Decision Orchestration."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.organization import Organization
    from app.models.user import User


class OrchestrationExecutionModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Execution ledger for end-to-end multi-modal query orchestration runs."""

    __tablename__ = "orchestration_executions"
    __table_args__ = (
        Index("ix_orchestration_exec_org_created_at", "organization_id", "created_at"),
        Index("ix_orchestration_exec_org_status", "organization_id", "status"),
        Index("ix_orchestration_exec_conversation", "conversation_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    mode: Mapped[str] = mapped_column(
        String(30),
        default="AUTO",
        nullable=False,
    )
    execution_strategy: Mapped[str] = mapped_column(
        String(30),
        default="NONE",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="RECEIVED",
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(
        String(50),
        default="ANSWER",
        nullable=False,
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.0"),
        nullable=False,
    )
    evidence_coverage: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.0"),
        nullable=False,
    )
    answer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    clarification_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    warnings: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    diagnostics: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    user: Mapped["User"] = relationship("User")
    conversation: Mapped["Conversation | None"] = relationship("Conversation")
    steps: Mapped[list["OrchestrationStepModel"]] = relationship(
        "OrchestrationStepModel",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="OrchestrationStepModel.step_order",
    )


class OrchestrationStepModel(Base, UUIDPrimaryKeyMixin):
    """Detailed audit trace for each discrete step in an orchestration execution."""

    __tablename__ = "orchestration_steps"
    __table_args__ = (
        UniqueConstraint("execution_id", "step_order", name="uq_orchestration_steps_order"),
        Index("ix_orchestration_steps_exec_order", "execution_id", "step_order"),
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orchestration_executions.id", ondelete="CASCADE"),
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
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    execution: Mapped["OrchestrationExecutionModel"] = relationship(
        "OrchestrationExecutionModel",
        back_populates="steps",
    )
