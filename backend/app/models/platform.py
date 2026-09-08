"""SQLAlchemy models for Enterprise Platform, API & Streaming Execution Events — TASK 34."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.orchestration import OrchestrationExecutionModel
    from app.models.organization import Organization


class ExecutionEventModel(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Persistent audit and replay ledger for real-time streaming execution events."""

    __tablename__ = "execution_events"
    __table_args__ = (
        UniqueConstraint("execution_id", "sequence", name="uq_execution_events_sequence"),
        Index("ix_execution_events_exec_seq", "execution_id", "sequence"),
        Index("ix_execution_events_org_created", "organization_id", "created_at"),
        Index("ix_execution_events_type", "event_type"),
    )

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("orchestration_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    execution: Mapped["OrchestrationExecutionModel"] = relationship("OrchestrationExecutionModel")
    organization: Mapped["Organization"] = relationship("Organization")
