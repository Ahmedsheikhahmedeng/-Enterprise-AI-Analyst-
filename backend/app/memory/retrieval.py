"""Hybrid memory retrieval combining Qdrant vector similarity and PostgreSQL metadata filtering."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.config import MemoryConfig, get_memory_config
from app.memory.models import MemoryItem
from app.memory.policies import MemoryAccessPolicy
from app.memory.ranking import MemoryRanker
from app.memory.schemas import (
    MemoryItemResponse,
    MemorySearchResultItem,
    MemoryStatus,
    MemoryType,
)
from app.memory.stores.vector import QdrantMemoryVectorStore


class MemoryRetriever:
    """Hybrid memory search coordinating vector indices and relational constraints."""

    def __init__(
        self,
        vector_store: QdrantMemoryVectorStore | None = None,
        ranker: MemoryRanker | None = None,
        config: MemoryConfig | None = None,
    ) -> None:
        self.vector_store = vector_store or QdrantMemoryVectorStore()
        self.ranker = ranker or MemoryRanker()
        self.config = config or get_memory_config()

    async def search(
        self,
        db_session: AsyncSession,
        query: str,
        organization_id: uuid.UUID,
        top_k: int = 5,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
        memory_types: list[MemoryType] | None = None,
        min_confidence: float | None = None,
        min_importance: float | None = None,
        user_permissions: set[str] | None = None,
    ) -> list[MemorySearchResultItem]:
        """Perform verified hybrid search ensuring deleted or expired memories are never returned."""
        # 1. Vector Search
        vector_hits = await self.vector_store.search_vectors(
            query=query,
            organization_id=organization_id,
            top_k=top_k * 2,
            user_id=user_id,
            session_id=session_id,
        )
        vector_score_map: dict[uuid.UUID, float] = dict(vector_hits)

        # 2. Relational Query (Canonical verification)
        stmt = select(MemoryItem).where(
            MemoryItem.organization_id == organization_id,
            MemoryItem.status == MemoryStatus.ACTIVE.value,
        )

        now = datetime.now(UTC)
        stmt = stmt.where((MemoryItem.expires_at.is_(None)) | (MemoryItem.expires_at > now))

        if memory_types:
            type_vals = [t.value if hasattr(t, "value") else str(t) for t in memory_types]
            stmt = stmt.where(MemoryItem.memory_type.in_(type_vals))

        if min_confidence is not None:
            stmt = stmt.where(MemoryItem.confidence >= min_confidence)

        if min_importance is not None:
            stmt = stmt.where(MemoryItem.importance >= min_importance)

        # If vector hits found, prioritize those IDs; otherwise perform metadata search
        if vector_score_map:
            stmt = stmt.where(MemoryItem.id.in_(list(vector_score_map.keys())))
        else:
            # Metadata text match fallback if vector search yielded no hits or vectorstore disabled
            stmt = stmt.where(MemoryItem.content.ilike(f"%{query[:50]}%"))

        res = await db_session.execute(stmt)
        candidates = list(res.scalars().all())

        # If still empty and vector search was skipped, fetch recent active memories
        if not candidates and not vector_score_map:
            fallback_stmt = (
                select(MemoryItem)
                .where(
                    MemoryItem.organization_id == organization_id,
                    MemoryItem.status == MemoryStatus.ACTIVE.value,
                    (MemoryItem.expires_at.is_(None)) | (MemoryItem.expires_at > now),
                )
                .order_by(MemoryItem.created_at.desc())
                .limit(top_k)
            )
            candidates = list((await db_session.execute(fallback_stmt)).scalars().all())

        results: list[MemorySearchResultItem] = []
        for item in candidates:
            # Check access policy
            try:
                MemoryAccessPolicy.authorize_read(
                    memory_item=item,
                    caller_org_id=organization_id,
                    caller_user_id=user_id,
                    caller_session_id=session_id,
                    user_permissions=user_permissions,
                )
            except Exception:
                continue

            sim = vector_score_map.get(item.id, 0.5)
            comp_score, breakdown = self.ranker.score_memory(
                memory_item=item,
                semantic_similarity=sim,
                target_session_id=session_id,
                now=now,
            )

            results.append(
                MemorySearchResultItem(
                    memory=MemoryItemResponse.model_validate(item),
                    relevance_score=comp_score,
                    score_breakdown=breakdown,
                )
            )

        # Sort by relevance_score descending
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:top_k]
