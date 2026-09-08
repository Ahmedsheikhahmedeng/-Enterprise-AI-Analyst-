"""Tenant-scoped repository for DocumentChunk entities."""

import uuid
from collections.abc import Sequence

from sqlalchemy import CursorResult, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.repositories.base import TenantScopedRepository


class DocumentChunkRepository(TenantScopedRepository[DocumentChunk]):
    """Tenant-isolated repository for managing chunk persistence and reprocessing."""

    def __init__(self) -> None:
        super().__init__(model=DocumentChunk)

    async def get_by_id(
        self,
        session: AsyncSession,
        id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> DocumentChunk | None:
        """Fetch a single chunk strictly scoped to tenant."""
        stmt = select(DocumentChunk).where(
            DocumentChunk.id == id,
            DocumentChunk.organization_id == organization_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(
        self,
        session: AsyncSession,
        ids: Sequence[uuid.UUID],
        organization_id: uuid.UUID,
    ) -> Sequence[DocumentChunk]:
        """Batch retrieve chunks strictly scoped to the tenant to eliminate N+1 queries."""
        if not ids:
            return []

        stmt = select(DocumentChunk).where(
            DocumentChunk.organization_id == organization_id,
            DocumentChunk.id.in_(ids),
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def list_by_document(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        parent_only: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[DocumentChunk]:
        """List chunks of document with optional parent filter, pagination, and tenant isolation."""
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.organization_id == organization_id,
                DocumentChunk.document_id == document_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
            .offset(skip)
            .limit(limit)
        )
        if parent_only:
            stmt = stmt.where(DocumentChunk.parent_chunk_id.is_(None))

        result = await session.execute(stmt)
        return result.scalars().all()

    async def count_by_document(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        parent_only: bool = False,
    ) -> int:
        """Count total chunks for a document within tenant scope."""
        stmt = select(func.count(DocumentChunk.id)).where(
            DocumentChunk.organization_id == organization_id,
            DocumentChunk.document_id == document_id,
        )
        if parent_only:
            stmt = stmt.where(DocumentChunk.parent_chunk_id.is_(None))

        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def delete_by_document(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> int:
        """Delete all chunks for a document scoped to tenant.

        Used during idempotent reprocessing to cleanly replace previous chunks
        without partial states or duplicates.
        """
        stmt = delete(DocumentChunk).where(
            DocumentChunk.organization_id == organization_id,
            DocumentChunk.document_id == document_id,
        )
        result = await session.execute(stmt)
        rowcount = result.rowcount if isinstance(result, CursorResult) else 0
        return int(rowcount)

    async def bulk_create(
        self,
        session: AsyncSession,
        chunks: list[DocumentChunk],
    ) -> Sequence[DocumentChunk]:
        """Bulk insert multiple document chunks efficiently."""
        if not chunks:
            return []

        session.add_all(chunks)
        await session.flush()
        return chunks
