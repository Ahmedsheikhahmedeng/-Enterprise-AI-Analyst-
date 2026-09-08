"""SQLAlchemy 2 database model for Distributed Background Jobs."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin


class Job(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Persistent database record for background jobs."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_org_status", "organization_id", "status"),
        Index("ix_jobs_type_status", "job_type", "status"),
        Index("ix_jobs_org_idempotency", "organization_id", "idempotency_key"),
        Index("ix_jobs_dedup_hash", "deduplication_hash"),
        Index("ix_jobs_status_retry", "status", "next_retry_at"),
        Index("ix_jobs_created_at", "created_at"),
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deduplication_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    progress: Mapped[float | None] = mapped_column(Float, default=0.0, nullable=True)
    progress_message: Mapped[str | None] = mapped_column(String(255), nullable=True)

    @property
    def job_id(self) -> uuid.UUID:
        """Alias for standard job_id references."""
        return self.id
