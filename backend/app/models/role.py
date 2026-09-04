import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class RolePermission(Base):
    """Many-to-Many association table linking Roles to granular Permissions."""

    __tablename__ = "role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Role definition supported for both system-wide and organization-specific RBAC."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_roles_org_name"),)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    organization: Mapped["Organization | None"] = relationship(
        "Organization",
        back_populates="roles",
    )
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
    )
    members: Mapped[list["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="role",
    )


class Permission(Base, UUIDPrimaryKeyMixin):
    """Granular platform permission entity defining explicit domain operations."""

    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
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
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
    )


class OrganizationMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Junction entity mapping Users to Organizations with an assigned Role."""

    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_members_org_user"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="members",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="organization_memberships",
    )
    role: Mapped["Role"] = relationship(
        "Role",
        back_populates="members",
    )
