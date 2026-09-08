import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AgentSession(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Central agent session orchestrating bounded execution within tenant boundaries."""

    __tablename__ = "agent_sessions"
    __table_args__ = (
        Index("ix_agent_sessions_org_status", "organization_id", "status"),
        Index("ix_agent_sessions_created_at", "created_at"),
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="created",
        index=True,
    )
    agent_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="analyst_agent",
    )
    goal: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    max_steps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=20,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
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
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    final_answer: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by],
    )
    plan: Mapped["AgentPlan | None"] = relationship(
        "AgentPlan",
        foreign_keys=[plan_id],
        post_update=True,
    )
    steps: Mapped[list["AgentStep"]] = relationship(
        "AgentStep",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentStep.sequence",
    )
    checkpoints: Mapped[list["AgentCheckpoint"]] = relationship(
        "AgentCheckpoint",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AgentCheckpoint.created_at",
    )
    approvals: Mapped[list["ApprovalRequest"]] = relationship(
        "ApprovalRequest",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AgentPlan(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Execution plan generated for an AgentSession containing bounded steps."""

    __tablename__ = "agent_plans"
    __table_args__ = (Index("ix_agent_plans_session_id", "session_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    goal: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    estimated_cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    estimated_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    estimated_duration: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AgentStep(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Single orchestrated action step within an AgentSession."""

    __tablename__ = "agent_steps"
    __table_args__ = (Index("ix_agent_steps_session_seq", "session_id", "sequence"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_plans.id", ondelete="SET NULL"),
        nullable=True,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    tool_input: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    output: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    evidence_refs: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    cost: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    duration_ms: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    session: Mapped["AgentSession"] = relationship(
        "AgentSession",
        back_populates="steps",
        foreign_keys=[session_id],
    )


class AgentCheckpoint(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Immutable state snapshot taken after each completed step for crash recovery and resume."""

    __tablename__ = "agent_checkpoints"
    __table_args__ = (Index("ix_agent_checkpoints_session_step", "session_id", "step_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_steps.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    tool_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    tool_input_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    tool_result_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    evidence_ids: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    state_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped["AgentSession"] = relationship(
        "AgentSession",
        back_populates="checkpoints",
    )


class ApprovalRequest(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Approval gate record requiring explicit operator sign-off before sensitive actions."""

    __tablename__ = "agent_approval_requests"
    __table_args__ = (Index("ix_agent_approval_requests_session_status", "session_id", "status"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_steps.id", ondelete="CASCADE"),
        nullable=False,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    session: Mapped["AgentSession"] = relationship(
        "AgentSession",
        back_populates="approvals",
    )
