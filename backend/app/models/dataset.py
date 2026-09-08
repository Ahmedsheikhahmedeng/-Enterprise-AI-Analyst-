import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.data_source import DataSource
    from app.models.organization import Organization
    from app.models.user import User


class Dataset(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Dataset entity representing structured tabular schemas accessible to the SQL Agent and downstream."""

    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_datasets_org_created_at", "organization_id", "created_at"),
        Index("ix_datasets_org_source_ds", "organization_id", "source_datasource_id"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="created",
        nullable=False,
    )
    row_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Ingestion & Materialization metadata (TASK 27)
    source_datasource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    visibility: Mapped[str] = mapped_column(
        String(32),
        default="internal",
        nullable=False,
    )
    classification: Mapped[str] = mapped_column(
        String(32),
        default="INTERNAL",
        nullable=False,
    )
    quality_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    ingestion_mode: Mapped[str] = mapped_column(
        String(32),
        default="structured_only",
        nullable=False,
    )
    watermark_column: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    last_watermark: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    source_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    schema_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    ingestion_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    profile_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    quality_report: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    lineage_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="datasets",
    )
    creator: Mapped["User | None"] = relationship("User")
    datasource: Mapped["DataSource | None"] = relationship("DataSource")
    columns: Mapped[list["DatasetColumn"]] = relationship(
        "DatasetColumn",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetColumn.ordinal_position",
    )
    versions: Mapped[list["DatasetVersion"]] = relationship(
        "DatasetVersion",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by=desc("version"),
    )


class DatasetColumn(Base, UUIDPrimaryKeyMixin):
    """Column metadata definition supporting schema-linking, profiling, and quality."""

    __tablename__ = "dataset_columns"
    __table_args__ = (
        UniqueConstraint("dataset_id", "name", name="uq_dataset_columns_dataset_name"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    normalized_name: Mapped[str] = mapped_column(
        String(100),
        default="",
        nullable=False,
    )
    original_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    data_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    nullable: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    ordinal_position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    pii_classification: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    stats: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        back_populates="columns",
    )


class DatasetVersion(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Immutable materialization snapshot version of a dataset."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        Index("ix_dataset_versions_dataset_version", "dataset_id", "version", unique=True),
        Index("ix_dataset_versions_org_dataset", "organization_id", "dataset_id"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ready",
        nullable=False,
    )
    row_count: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    schema_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    storage_path: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
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
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    dataset: Mapped["Dataset"] = relationship(
        "Dataset",
        back_populates="versions",
    )
    organization: Mapped["Organization"] = relationship("Organization")
    creator: Mapped["User | None"] = relationship("User")
