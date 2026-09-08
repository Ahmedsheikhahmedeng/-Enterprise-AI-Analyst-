import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import AnalysisRun
    from app.models.organization import Organization
    from app.models.user import User


class UsageEvent(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Aggregate quota and metered consumption event tracking."""

    __tablename__ = "usage_events"
    __table_args__ = (
        Index("ix_usage_events_org_created_at", "organization_id", "created_at"),
        Index("ix_usage_events_event_type", "event_type"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
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
        back_populates="usage_events",
    )
    user: Mapped["User | None"] = relationship("User")


class LLMRequest(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Granular execution ledger for external LLM invocations and cost accounting."""

    __tablename__ = "llm_requests"
    __table_args__ = (Index("ix_llm_requests_org_created_at", "organization_id", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trace_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    span_id: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    request_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 6),
        nullable=False,
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="success",
        nullable=False,
    )
    task_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    fallback_used: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    cache_hit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
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
        back_populates="llm_requests",
    )
    user: Mapped["User | None"] = relationship("User")
    analysis_run: Mapped["AnalysisRun | None"] = relationship("AnalysisRun")
