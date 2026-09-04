import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class Document(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Document entity representing ingested unstructured knowledge assets."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_org_created_at", "organization_id", "created_at"),
        Index("ix_documents_org_status", "organization_id", "status"),
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
        index=True,
    )
    page_count: Mapped[int | None] = mapped_column(
        Integer,
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
        back_populates="documents",
    )
    creator: Mapped["User | None"] = relationship("User")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base, UUIDPrimaryKeyMixin, TenantScopedMixin):
    """Extracted text slices linked to parent document and referenced in vector indices."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_chunk_idx"),
        Index("ix_doc_chunks_org_doc", "organization_id", "document_id"),
        Index("ix_doc_chunks_doc_idx", "document_id", "chunk_index"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    section: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    chunk_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
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
    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )
