"""Tenant-scoped repository for Document and nested DocumentChunk entities."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.repositories.base import TenantScopedRepository


class DocumentRepository(TenantScopedRepository[Document]):
    """Tenant-isolated repository for Documents and nested DocumentChunks."""

    def __init__(self) -> None:
        super().__init__(model=Document)

    async def get_by_id(
        self,
        session: AsyncSession,
        id: uuid.UUID,
        organization_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Document | None:
        """Fetch a single document strictly scoped to tenant, excluding soft-deleted by default."""
        stmt = select(Document).where(
            Document.id == id,
            Document.organization_id == organization_id,
        )
        if not include_deleted:
            stmt = stmt.where(
                Document.deleted_at.is_(None),
                Document.status != "deleted",
            )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False,
    ) -> Sequence[Document]:
        """List documents for organization, excluding soft-deleted documents by default."""
        stmt = (
            select(Document)
            .where(Document.organization_id == organization_id)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if not include_deleted:
            stmt = stmt.where(
                Document.deleted_at.is_(None),
                Document.status != "deleted",
            )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> int:
        """Count tenant documents, excluding soft-deleted documents by default."""
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.organization_id == organization_id)
        )
        if not include_deleted:
            stmt = stmt.where(
                Document.deleted_at.is_(None),
                Document.status != "deleted",
            )
        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_by_checksum(
        self,
        session: AsyncSession,
        organization_id: uuid.UUID,
        sha256: str,
        include_deleted: bool = False,
    ) -> Document | None:
        """Find an active document by SHA-256 hash strictly within the tenant scope."""
        stmt = select(Document).where(
            Document.organization_id == organization_id,
            Document.sha256 == sha256,
        )
        if not include_deleted:
            stmt = stmt.where(
                Document.deleted_at.is_(None),
                Document.status != "deleted",
            )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def soft_delete(
        self,
        session: AsyncSession,
        id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> bool:
        """Soft-delete document by marking status='deleted' and recording deleted_at timestamp."""
        stmt = (
            update(Document)
            .where(
                Document.id == id,
                Document.organization_id == organization_id,
                Document.deleted_at.is_(None),
            )
            .values(status="deleted", deleted_at=func.now())
        )
        result = await session.execute(stmt)
        rowcount = result.rowcount if isinstance(result, CursorResult) else 1
        await session.flush()
        return bool(rowcount > 0)

    async def get_chunk(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
        chunk_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> DocumentChunk | None:
        """Fetch a specific DocumentChunk verifying parent linkage and organization scope.

        Strictly prevents nested IDOR traversal by asserting:
        1. chunk.id == chunk_id
        2. chunk.document_id == document_id
        3. chunk.organization_id == organization_id
        """
        stmt = select(DocumentChunk).where(
            DocumentChunk.id == chunk_id,
            DocumentChunk.document_id == document_id,
            DocumentChunk.organization_id == organization_id,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_chunks(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Sequence[DocumentChunk]:
        """List chunks of document, verifying both document and organization ownership."""
        stmt = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.organization_id == organization_id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def create_chunk(
        self,
        session: AsyncSession,
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
        chunk_index: int,
        content: str,
        page_number: int | None = None,
        section: str | None = None,
        chunk_type: str | None = None,
        metadata_: dict[str, Any] | None = None,
    ) -> DocumentChunk:
        """Create a DocumentChunk ensuring parent document belongs to the same organization."""
        parent_doc = await self.get_by_id(session, id=document_id, organization_id=organization_id)
        if parent_doc is None:
            raise ValueError(
                f"Parent document {document_id} does not exist in organization {organization_id}."
            )

        chunk = DocumentChunk(
            document_id=document_id,
            organization_id=organization_id,
            chunk_index=chunk_index,
            content=content,
            page_number=page_number,
            section=section,
            chunk_type=chunk_type,
            metadata_=metadata_,
        )
        session.add(chunk)
        await session.flush()
        return chunk
