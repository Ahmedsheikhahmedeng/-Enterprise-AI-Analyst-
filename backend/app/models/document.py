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
    text,
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
        Index("ix_documents_org_deleted_at", "organization_id", "deleted_at"),
        Index(
            "uq_documents_org_sha256_active",
            "organization_id",
            "sha256",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND status != 'deleted' AND sha256 != ''"),
        ),
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
    detected_mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
    )
    storage_backend: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="local",
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
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    parsed_storage_key: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    parser_name: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    parser_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    parsed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
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
        Index("ix_doc_chunks_parent", "parent_chunk_id"),
        Index("ix_doc_chunks_org_hash", "organization_id", "content_hash"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=True,
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    chunk_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    heading_context: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    heading_path: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    page_number: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    section: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    source_locator: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        server_default="",
        index=True,
    )
    chunker_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
        server_default="1.0.0",
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
    parent: Mapped["DocumentChunk | None"] = relationship(
        "DocumentChunk",
        remote_side="DocumentChunk.id",
        back_populates="children",
    )
    children: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[list["DocumentChunkEmbedding"]] = relationship(
        "DocumentChunkEmbedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
    )


class DocumentChunkEmbedding(Base, UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Metadata tracking generated dense vector embeddings for document chunks.

    Dense vector payloads reside in vector stores (Qdrant), while this table
    tracks generation provenance, model versions, hashes, and indexing status.
    """

    __tablename__ = "document_chunk_embeddings"
    __table_args__ = (
        Index("ix_chunk_embeddings_org_chunk", "organization_id", "chunk_id"),
        Index("ix_chunk_embeddings_org_doc", "organization_id", "document_id"),
        Index("ix_chunk_embeddings_hash", "organization_id", "embedding_input_hash"),
        Index("ix_chunk_embeddings_status", "organization_id", "status"),
        Index("ix_chunk_embeddings_org_indexing", "organization_id", "indexing_status"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="local",
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
    )
    dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    normalization: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="l2",
    )
    embedding_input_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
        nullable=False,
        index=True,
    )
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    indexing_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        server_default="pending",
        nullable=False,
        index=True,
    )
    point_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document")

    chunk: Mapped["DocumentChunk"] = relationship(
        "DocumentChunk",
        back_populates="embeddings",
    )
