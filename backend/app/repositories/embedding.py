"""Tenant-scoped repository for DocumentChunkEmbedding entities."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunkEmbedding
from app.repositories.base import TenantScopedRepository


class DocumentChunkEmbeddingRepository(TenantScopedRepository[DocumentChunkEmbedding]):
    """Tenant-isolated repository for managing chunk embedding metadata persistence."""

    def __init__(self) -> None:
        super().__init__(model=DocumentChunkEmbedding)

    async def get_by_id(
        self,
        session: AsyncSession,
        id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> DocumentChunkEmbedding | None:
        """Fetch single embedding record strictly scoped to tenant."""
        stmt = select(DocumentChunkEmbedding).where(
            DocumentChunkEmbedding.id == id,
            DocumentChunkEmbedding.organization_id == organization_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_document(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        skip: int = 0,
        limit: int = 1000,
    ) -> Sequence[DocumentChunkEmbedding]:
        """List embedding records of a document with tenant isolation."""
        stmt = (
            select(DocumentChunkEmbedding)
            .where(
                DocumentChunkEmbedding.organization_id == organization_id,
                DocumentChunkEmbedding.document_id == document_id,
            )
            .order_by(DocumentChunkEmbedding.created_at.asc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def count_by_document(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        status: str | None = None,
    ) -> int:
        """Count embedding records for a document within tenant scope."""
        stmt = select(func.count(DocumentChunkEmbedding.id)).where(
            DocumentChunkEmbedding.organization_id == organization_id,
            DocumentChunkEmbedding.document_id == document_id,
        )
        if status:
            stmt = stmt.where(DocumentChunkEmbedding.status == status)

        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def delete_by_document(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        """Delete all embedding records for a document scoped to tenant.

        Used during idempotent re-embedding to cleanly replace previous embedding metadata.
        """
        stmt = delete(DocumentChunkEmbedding).where(
            DocumentChunkEmbedding.organization_id == organization_id,
            DocumentChunkEmbedding.document_id == document_id,
        )
        result = await session.execute(stmt)
        rowcount = result.rowcount if isinstance(result, CursorResult) else 0
        return int(rowcount)

    async def get_by_chunk_and_hash(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        chunk_id: uuid.UUID,
        embedding_input_hash: str,
    ) -> DocumentChunkEmbedding | None:
        """Check for existing embedding for a chunk matching the cryptographic input hash."""
        stmt = select(DocumentChunkEmbedding).where(
            DocumentChunkEmbedding.organization_id == organization_id,
            DocumentChunkEmbedding.chunk_id == chunk_id,
            DocumentChunkEmbedding.embedding_input_hash == embedding_input_hash,
            DocumentChunkEmbedding.status == "completed",
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_create(
        self,
        session: AsyncSession,
        embeddings: list[DocumentChunkEmbedding],
    ) -> Sequence[DocumentChunkEmbedding]:
        """Bulk insert multiple document chunk embedding records efficiently."""
        if not embeddings:
            return []

        session.add_all(embeddings)
        await session.flush()
        return embeddings

    async def update_indexing_status(
        self,
        session: AsyncSession,
        embedding_id: uuid.UUID,
        organization_id: uuid.UUID,
        point_id: uuid.UUID,
        status: str = "indexed",
        indexed_at: datetime | None = None,
    ) -> None:
        """Update indexing status, point ID, and timestamp for an embedding record."""
        stmt = select(DocumentChunkEmbedding).where(
            DocumentChunkEmbedding.id == embedding_id,
            DocumentChunkEmbedding.organization_id == organization_id,
        )
        rec = (await session.execute(stmt)).scalar_one_or_none()
        if rec:
            rec.indexing_status = status
            rec.point_id = point_id
            rec.indexed_at = indexed_at or datetime.now(UTC)
            await session.flush()

    async def count_by_indexing_status(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        indexing_status: str,
    ) -> int:
        """Count embedding records by their vector indexing status."""
        stmt = select(func.count(DocumentChunkEmbedding.id)).where(
            DocumentChunkEmbedding.organization_id == organization_id,
            DocumentChunkEmbedding.document_id == document_id,
            DocumentChunkEmbedding.indexing_status == indexing_status,
        )
        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)
