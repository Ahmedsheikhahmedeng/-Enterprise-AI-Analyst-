"""Deletion service implementing soft tombstones and vector index eviction."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.exceptions import MemoryNotFoundError
from app.memory.models import MemoryItem
from app.memory.policies import MemoryAccessPolicy
from app.memory.schemas import MemoryStatus
from app.memory.stores.vector import QdrantMemoryVectorStore


class MemoryDeletionService:
    """Manages soft-deletion tombstones and vector index cleanup."""

    def __init__(self, vector_store: QdrantMemoryVectorStore | None = None) -> None:
        self.vector_store = vector_store or QdrantMemoryVectorStore()

    async def delete_memory(
        self,
        db_session: AsyncSession,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        user_permissions: set[str] | None = None,
    ) -> MemoryItem:
        """Soft-delete a single memory item and purge its vector point."""
        stmt = select(MemoryItem).where(
            MemoryItem.id == memory_id,
            MemoryItem.organization_id == organization_id,
            MemoryItem.status != MemoryStatus.DELETED.value,
        )
        res = await db_session.execute(stmt)
        item = res.scalars().first()
        if not item:
            raise MemoryNotFoundError(memory_id)

        # Check access policy
        MemoryAccessPolicy.authorize_read(
            memory_item=item,
            caller_org_id=organization_id,
            caller_user_id=user_id,
            user_permissions=user_permissions,
        )

        item.status = MemoryStatus.DELETED.value
        item.deleted_at = datetime.now(UTC)
        item.deleted_by = user_id
        await db_session.flush()

        # Evict from vector index
        await self.vector_store.delete_memory_vector(
            memory_id=memory_id,
            organization_id=organization_id,
        )

        return item

    async def delete_user_memories(
        self,
        db_session: AsyncSession,
        target_user_id: uuid.UUID,
        organization_id: uuid.UUID,
        deleted_by: uuid.UUID | None = None,
    ) -> int:
        """Delete all memories associated with a specific user in an organization."""
        stmt = select(MemoryItem).where(
            MemoryItem.organization_id == organization_id,
            MemoryItem.user_id == target_user_id,
            MemoryItem.status != MemoryStatus.DELETED.value,
        )
        res = await db_session.execute(stmt)
        items = list(res.scalars().all())

        now = datetime.now(UTC)
        for it in items:
            it.status = MemoryStatus.DELETED.value
            it.deleted_at = now
            it.deleted_by = deleted_by
            await self.vector_store.delete_memory_vector(it.id, organization_id)

        await db_session.flush()
        return len(items)

    async def delete_session_memories(
        self,
        db_session: AsyncSession,
        session_id: uuid.UUID,
        organization_id: uuid.UUID,
        deleted_by: uuid.UUID | None = None,
    ) -> int:
        """Delete all working and short-term memories tied to a session."""
        stmt = select(MemoryItem).where(
            MemoryItem.organization_id == organization_id,
            MemoryItem.session_id == session_id,
            MemoryItem.status != MemoryStatus.DELETED.value,
        )
        res = await db_session.execute(stmt)
        items = list(res.scalars().all())

        now = datetime.now(UTC)
        for it in items:
            it.status = MemoryStatus.DELETED.value
            it.deleted_at = now
            it.deleted_by = deleted_by
            await self.vector_store.delete_memory_vector(it.id, organization_id)

        await db_session.flush()
        return len(items)
