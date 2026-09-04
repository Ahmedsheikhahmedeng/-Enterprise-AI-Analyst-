import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String
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
