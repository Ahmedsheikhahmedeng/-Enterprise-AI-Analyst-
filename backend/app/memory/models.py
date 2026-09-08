"""SQLAlchemy domain models for Enterprise Agent Memory."""

import uuid
from datetime import datetime
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, UUIDPrimaryKeyMixin


class MemoryItem(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Canonical memory item representing short-term, working, episodic, or semantic memory."""

    __tablename__ = "memory_items"
    __table_args__ = (
        Index("ix_memory_items_org_status", "organization_id", "status"),
        Index("ix_memory_items_org_type", "organization_id", "memory_type"),
        Index("ix_memory_items_org_user", "organization_id", "user_id"),
        Index("ix_memory_items_org_session", "organization_id", "session_id"),
        Index("ix_memory_items_org_hash", "organization_id", "content_hash"),
        Index("ix_memory_items_org_expires", "organization_id", "expires_at"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    memory_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # short_term, working, episodic, semantic
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    importance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="user_declared",
    )  # user_declared, agent_derived, document_derived, system_verified
    source_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="organization",
    )  # private, user, organization, session
    privacy_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="normal",
    )  # normal, sensitive, restricted
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
    )  # active, superseded, stale, deleted
    supersedes_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    meta_info: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    # Relationships
    versions: Mapped[list["MemoryVersion"]] = relationship(
        "MemoryVersion",
        back_populates="memory_item",
        cascade="all, delete-orphan",
        order_by="MemoryVersion.version.desc()",
    )


class MemoryVersion(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Immutable historical version snapshot of a memory item."""

    __tablename__ = "memory_versions"
    __table_args__ = (Index("ix_memory_versions_memory_version", "memory_id", "version"),)

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memory_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    importance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    memory_item: Mapped["MemoryItem"] = relationship(
        "MemoryItem",
        back_populates="versions",
    )
