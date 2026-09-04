import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Dataset(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Dataset entity representing structured tabular schemas accessible to the SQL Agent."""

    __tablename__ = "datasets"
    __table_args__ = (Index("ix_datasets_org_created_at", "organization_id", "created_at"),)

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
        default="active",
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

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="datasets",
    )
    creator: Mapped["User | None"] = relationship("User")
    columns: Mapped[list["DatasetColumn"]] = relationship(
        "DatasetColumn",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetColumn.ordinal_position",
    )


class DatasetColumn(Base, UUIDPrimaryKeyMixin):
    """Column metadata definition supporting schema-linking in Text-to-SQL workflows."""

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
