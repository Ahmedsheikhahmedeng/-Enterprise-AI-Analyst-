"""Tenant-scoped repository for Document and nested DocumentChunk entities."""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.repositories.base import TenantScopedRepository


class DocumentRepository(TenantScopedRepository[Document]):
    """Tenant-isolated repository for Documents and nested DocumentChunks."""

    def __init__(self) -> None:
        super().__init__(model=Document)

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
