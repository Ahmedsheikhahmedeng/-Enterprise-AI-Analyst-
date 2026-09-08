"""Base protocols for memory storage backends."""

import uuid
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import MemoryItem
from app.memory.schemas import MemoryCandidate


class MemoryMetadataStore(Protocol):
    """Protocol for persisting and querying memory metadata in relational database."""

    async def save(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        candidate: MemoryCandidate,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        expires_at: Any | None = None,
        content_hash: str | None = None,
    ) -> MemoryItem: ...

    async def get_by_id(
        self,
        db_session: AsyncSession,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> MemoryItem | None: ...

    async def find_by_content_hash(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        content_hash: str,
    ) -> MemoryItem | None: ...


class MemoryVectorStore(Protocol):
    """Protocol for indexing and searching memory vector embeddings."""

    async def index_memory(
        self,
        memory_item: MemoryItem,
    ) -> None: ...

    async def search_vectors(
        self,
        query: str,
        organization_id: uuid.UUID,
        top_k: int = 5,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
    ) -> list[tuple[uuid.UUID, float]]:
        """Return list of (memory_id, similarity_score) tuples."""
        ...

    async def delete_memory_vector(
        self,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None: ...
