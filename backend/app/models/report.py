import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
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
    current_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
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
    versions: Mapped[list["ReportVersion"]] = relationship(
        "ReportVersion",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportVersion.version_number",
    )


class ReportVersion(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Immutable or draft version snapshot of a business intelligence report."""

    __tablename__ = "report_versions"
    __table_args__ = (
        UniqueConstraint("report_id", "version_number", name="uq_report_versions_report_version"),
        Index("ix_report_versions_report_id", "report_id"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
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
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    document_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
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
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="versions",
    )
    creator: Mapped["User | None"] = relationship("User")
    organization: Mapped["Organization"] = relationship("Organization")
