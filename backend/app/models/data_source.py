import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class DataSource(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """External relational databases or data stores connected to an organization."""

    __tablename__ = "data_sources"
    __table_args__ = (Index("ix_data_sources_org_type", "organization_id", "type"),)

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        nullable=False,
    )
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="data_sources",
    )
    creator: Mapped["User | None"] = relationship("User")
    sync_runs: Mapped[list["DataSourceSyncRun"]] = relationship(
        "DataSourceSyncRun",
        back_populates="data_source",
        cascade="all, delete-orphan",
    )


class DataSourceSyncRun(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Execution history of a background synchronization for a DataSource."""

    __tablename__ = "data_source_sync_runs"
    __table_args__ = (
        Index("ix_ds_sync_runs_org_ds", "organization_id", "data_source_id"),
        Index("ix_ds_sync_runs_org_status", "organization_id", "status"),
        Index("ix_ds_sync_runs_created_at", "created_at"),
    )

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sync_type: Mapped[str] = mapped_column(
        String(50),
        default="full",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
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
    rows_synced: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    meta_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Relationships
    data_source: Mapped["DataSource"] = relationship(
        "DataSource",
        back_populates="sync_runs",
    )
