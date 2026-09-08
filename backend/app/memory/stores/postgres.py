"""PostgreSQL implementation of MemoryMetadataStore."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.models import MemoryItem, MemoryVersion
from app.memory.normalization import compute_content_hash
from app.memory.schemas import MemoryCandidate, MemoryStatus, MemoryType


class PostgresMemoryMetadataStore:
    """Relational database store for canonical memory records."""

    async def save(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        candidate: MemoryCandidate,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        expires_at: datetime | None = None,
        content_hash: str | None = None,
    ) -> MemoryItem:
        """Persist a new memory item."""
        c_hash = content_hash or compute_content_hash(candidate.content)

        item = MemoryItem(
            organization_id=organization_id,
            user_id=user_id,
            session_id=session_id or candidate.source_id
            if candidate.source_type == "agent_derived"
            else session_id,
            memory_type=str(
                candidate.memory_type.value
                if hasattr(candidate.memory_type, "value")
                else candidate.memory_type
            ),
            content=candidate.content,
            summary=candidate.summary,
            importance=candidate.importance,
            confidence=candidate.confidence,
            source_type=str(
                candidate.source_type.value
                if hasattr(candidate.source_type, "value")
                else candidate.source_type
            ),
            source_id=candidate.source_id,
            source_refs=candidate.source_refs,
            expires_at=expires_at,
            version=1,
            content_hash=c_hash,
            visibility=str(
                candidate.visibility.value
                if hasattr(candidate.visibility, "value")
                else candidate.visibility
            ),
            privacy_level=str(
                candidate.privacy_level.value
                if hasattr(candidate.privacy_level, "value")
                else candidate.privacy_level
            ),
            status=MemoryStatus.ACTIVE.value,
            supersedes_memory_id=candidate.supersedes_memory_id,
            meta_info={},
        )
        db_session.add(item)
        await db_session.flush()

        # Create initial version
        version = MemoryVersion(
            organization_id=organization_id,
            memory_id=item.id,
            version=1,
            content=item.content,
            summary=item.summary,
            importance=item.importance,
            confidence=item.confidence,
        )
        db_session.add(version)
        await db_session.flush()

        return item

    async def get_by_id(
        self,
        db_session: AsyncSession,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> MemoryItem | None:
        """Fetch memory item by ID within tenant boundary."""
        stmt = select(MemoryItem).where(
            MemoryItem.id == memory_id,
            MemoryItem.organization_id == organization_id,
        )
        if not include_deleted:
            stmt = stmt.where(MemoryItem.status != MemoryStatus.DELETED.value)
        res = await db_session.execute(stmt)
        return res.scalars().first()

    async def find_by_content_hash(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        content_hash: str,
        active_only: bool = True,
    ) -> MemoryItem | None:
        """Locate memory item with matching content hash in tenant."""
        stmt = select(MemoryItem).where(
            MemoryItem.organization_id == organization_id,
            MemoryItem.content_hash == content_hash,
        )
        if active_only:
            stmt = stmt.where(MemoryItem.status == MemoryStatus.ACTIVE.value)
        res = await db_session.execute(stmt)
        return res.scalars().first()

    async def list_memories(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        memory_types: list[MemoryType] | None = None,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[MemoryItem], int]:
        """Fetch paginated memories for an organization."""
        stmt = select(MemoryItem).where(MemoryItem.organization_id == organization_id)

        if active_only:
            stmt = stmt.where(MemoryItem.status == MemoryStatus.ACTIVE.value)
            # Filter out expired items
            now = datetime.now(UTC)
            stmt = stmt.where((MemoryItem.expires_at.is_(None)) | (MemoryItem.expires_at > now))

        if memory_types:
            type_vals = [t.value if hasattr(t, "value") else str(t) for t in memory_types]
            stmt = stmt.where(MemoryItem.memory_type.in_(type_vals))

        if user_id:
            stmt = stmt.where(
                (MemoryItem.user_id == user_id) | (MemoryItem.visibility == "organization")
            )

        if session_id:
            stmt = stmt.where(MemoryItem.session_id == session_id)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_count = (await db_session.execute(count_stmt)).scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        stmt = stmt.order_by(MemoryItem.created_at.desc()).offset(offset).limit(page_size)
        res = await db_session.execute(stmt)
        return list(res.scalars().all()), total_count

    async def get_summary_counts(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Compute aggregated counts by memory_type, status, and privacy_level."""
        # Total
        tot_stmt = select(func.count(MemoryItem.id)).where(
            MemoryItem.organization_id == organization_id,
            MemoryItem.status != MemoryStatus.DELETED.value,
        )
        total = (await db_session.execute(tot_stmt)).scalar() or 0

        # By type
        type_stmt = (
            select(MemoryItem.memory_type, func.count(MemoryItem.id))
            .where(
                MemoryItem.organization_id == organization_id,
                MemoryItem.status != MemoryStatus.DELETED.value,
            )
            .group_by(MemoryItem.memory_type)
        )
        type_rows = (await db_session.execute(type_stmt)).all()
        by_type: dict[str, int] = {str(row[0]): int(row[1]) for row in type_rows}

        # By status
        status_stmt = (
            select(MemoryItem.status, func.count(MemoryItem.id))
            .where(MemoryItem.organization_id == organization_id)
            .group_by(MemoryItem.status)
        )
        status_rows = (await db_session.execute(status_stmt)).all()
        by_status: dict[str, int] = {str(row[0]): int(row[1]) for row in status_rows}

        # By privacy
        priv_stmt = (
            select(MemoryItem.privacy_level, func.count(MemoryItem.id))
            .where(
                MemoryItem.organization_id == organization_id,
                MemoryItem.status != MemoryStatus.DELETED.value,
            )
            .group_by(MemoryItem.privacy_level)
        )
        priv_rows = (await db_session.execute(priv_stmt)).all()
        by_privacy: dict[str, int] = {str(row[0]): int(row[1]) for row in priv_rows}

        return {
            "total_memories": total,
            "by_type": by_type,
            "by_status": by_status,
            "by_privacy": by_privacy,
        }
