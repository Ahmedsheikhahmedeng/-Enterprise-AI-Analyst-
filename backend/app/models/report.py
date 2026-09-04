import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import AnalysisRun
    from app.models.organization import Organization
    from app.models.user import User


class Report(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Business intelligence report synthesized from analysis runs and evidence."""

    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_org_created_at", "organization_id", "created_at"),)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
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
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False,
    )
    # Content is stored as TEXT for native Markdown readability, rendering, and diffing.
    # Structured chart specifications and metadata are stored in JSONB.
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="reports",
    )
    creator: Mapped["User | None"] = relationship("User")
    analysis_run: Mapped["AnalysisRun | None"] = relationship(
        "AnalysisRun",
        back_populates="reports",
    )
