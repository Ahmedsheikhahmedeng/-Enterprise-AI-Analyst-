"""Central MemoryService orchestrating lifecycle, privacy, indexing, and search."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.config import MemoryConfig, get_memory_config
from app.memory.deduplication import (
    MemoryConflictDetector,
    MemoryDeduplicator,
)
from app.memory.deletion import MemoryDeletionService
from app.memory.exceptions import (
    MemoryNotFoundError,
)
from app.memory.models import MemoryItem, MemoryVersion
from app.memory.normalization import compute_content_hash
from app.memory.permissions import require_memory_permission
from app.memory.policies import MemoryAccessPolicy, MemoryPrivacyFilter
from app.memory.retention import MemoryRetentionPolicy
from app.memory.retrieval import MemoryRetriever
from app.memory.schemas import (
    MemoryCandidate,
    MemoryItemCreateRequest,
    MemoryItemUpdateRequest,
    MemorySearchRequest,
    MemorySearchResultItem,
    MemorySourceType,
    MemoryStatus,
    MemorySummaryResponse,
    MemoryType,
)
from app.memory.stores.postgres import PostgresMemoryMetadataStore
from app.memory.stores.vector import QdrantMemoryVectorStore
from app.models.audit import AuditLog
from app.observability.instrumentation.memory import (
    MemoryInstrumentation,
    get_memory_instrumentation,
)
from app.rbac.catalog import (
    PERM_MEMORY_CREATE,
    PERM_MEMORY_DELETE,
    PERM_MEMORY_READ,
    PERM_MEMORY_UPDATE,
)


class MemoryService:
    """Enterprise memory orchestration service implementing bounded, privacy-governed memory."""

    def __init__(
        self,
        config: MemoryConfig | None = None,
        metadata_store: PostgresMemoryMetadataStore | None = None,
        vector_store: QdrantMemoryVectorStore | None = None,
        retriever: MemoryRetriever | None = None,
        retention_policy: MemoryRetentionPolicy | None = None,
        deletion_service: MemoryDeletionService | None = None,
        instrumentation: MemoryInstrumentation | None = None,
    ) -> None:
        self.config = config or get_memory_config()
        self.metadata_store = metadata_store or PostgresMemoryMetadataStore()
        self.vector_store = vector_store or QdrantMemoryVectorStore(self.config)
        self.retriever = retriever or MemoryRetriever(
            vector_store=self.vector_store,
            config=self.config,
        )
        self.retention_policy = retention_policy or MemoryRetentionPolicy(self.config)
        self.deletion_service = deletion_service or MemoryDeletionService(self.vector_store)
        self.deduplicator = MemoryDeduplicator(self.config)
        self.conflict_detector = MemoryConflictDetector()
        self.instrumentation = instrumentation or get_memory_instrumentation()

    async def create_memory(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        request: MemoryItemCreateRequest,
        user_id: uuid.UUID | None = None,
        user_permissions: set[str] | None = None,
    ) -> MemoryItem:
        """Validate, deduplicate, and persist a memory candidate."""
        perms = user_permissions or set()
        require_memory_permission(perms, PERM_MEMORY_CREATE)
        MemoryAccessPolicy.authorize_write(request.privacy_level, perms)

        # 1. Privacy Filter: Disallow credentials and secret tokens
        MemoryPrivacyFilter.enforce(request.content)

        content_hash = compute_content_hash(request.content)

        # 2. Check exact duplicate
        existing = await self.metadata_store.find_by_content_hash(
            db_session=db_session,
            organization_id=organization_id,
            content_hash=content_hash,
            active_only=True,
        )
        if existing:
            return existing

        candidate = MemoryCandidate(
            memory_type=request.memory_type,
            content=request.content,
            summary=request.summary,
            importance=request.importance,
            confidence=request.confidence,
            source_type=MemorySourceType.USER_DECLARED,
            source_id=str(user_id) if user_id else None,
            source_refs=request.source_refs,
            visibility=request.visibility,
            privacy_level=request.privacy_level,
            supersedes_memory_id=request.supersedes_memory_id,
        )

        # 3. Conflict Detection with previous superseded memory if referenced
        if request.supersedes_memory_id:
            old_item = await self.metadata_store.get_by_id(
                db_session=db_session,
                memory_id=request.supersedes_memory_id,
                organization_id=organization_id,
            )
            if old_item:
                old_item.status = MemoryStatus.SUPERSEDED.value
                await db_session.flush()

        # 4. Retention expiration
        expires_at = self.retention_policy.compute_expiration(request.memory_type)

        # 5. Persist to Postgres
        item = await self.metadata_store.save(
            db_session=db_session,
            organization_id=organization_id,
            candidate=candidate,
            user_id=user_id,
            session_id=request.session_id,
            expires_at=expires_at,
            content_hash=content_hash,
        )

        # 6. Index into Qdrant
        await self.vector_store.index_memory(item)

        # 7. Audit log
        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="memory.created",
                resource_type="memory_item",
                resource_id=str(item.id),
            )
        )
        await db_session.commit()
        await db_session.refresh(item)
        self.instrumentation.record_memory_write(item.memory_type)
        return item

    async def get_memory(
        self,
        db_session: AsyncSession,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        user_permissions: set[str] | None = None,
    ) -> MemoryItem:
        """Fetch single memory item with access authorization."""
        perms = user_permissions or set()
        require_memory_permission(perms, PERM_MEMORY_READ)

        item = await self.metadata_store.get_by_id(
            db_session=db_session,
            memory_id=memory_id,
            organization_id=organization_id,
        )
        if not item:
            raise MemoryNotFoundError(memory_id)

        MemoryAccessPolicy.authorize_read(
            memory_item=item,
            caller_org_id=organization_id,
            caller_user_id=user_id,
            user_permissions=perms,
        )
        self.instrumentation.record_memory_read(item.memory_type)
        return item

    async def search_memories(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        request: MemorySearchRequest,
        user_id: uuid.UUID | None = None,
        user_permissions: set[str] | None = None,
    ) -> list[MemorySearchResultItem]:
        """Perform semantic and metadata hybrid search."""
        import time

        perms = user_permissions or set()
        require_memory_permission(perms, PERM_MEMORY_READ)

        t0 = time.perf_counter()
        results = await self.retriever.search(
            db_session=db_session,
            query=request.query,
            organization_id=organization_id,
            top_k=request.top_k,
            user_id=user_id,
            session_id=request.session_id,
            memory_types=request.memory_types,
            min_confidence=request.min_confidence,
            min_importance=request.min_importance,
            user_permissions=perms,
        )
        duration_ms = (time.perf_counter() - t0) * 1000

        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="memory.search",
                resource_type="memory_item",
                resource_id="query",
            )
        )
        await db_session.commit()
        self.instrumentation.record_memory_search(duration_ms=duration_ms, hits_count=len(results))
        return results

    async def list_memories(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        memory_types: list[MemoryType] | None = None,
        user_id: uuid.UUID | None = None,
        page: int = 1,
        page_size: int = 50,
        user_permissions: set[str] | None = None,
    ) -> tuple[list[MemoryItem], int]:
        """List paginated memory items for tenant."""
        perms = user_permissions or set()
        require_memory_permission(perms, PERM_MEMORY_READ)

        return await self.metadata_store.list_memories(
            db_session=db_session,
            organization_id=organization_id,
            memory_types=memory_types,
            user_id=user_id,
            page=page,
            page_size=min(page_size, 100),
        )

    async def get_summary(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        user_permissions: set[str] | None = None,
    ) -> MemorySummaryResponse:
        """Fetch summary counts of memory tiers."""
        perms = user_permissions or set()
        require_memory_permission(perms, PERM_MEMORY_READ)

        counts = await self.metadata_store.get_summary_counts(
            db_session=db_session,
            organization_id=organization_id,
        )
        return MemorySummaryResponse(
            organization_id=organization_id,
            total_memories=counts["total_memories"],
            by_type=counts["by_type"],
            by_status=counts["by_status"],
            by_privacy=counts["by_privacy"],
        )

    async def delete_memory(
        self,
        db_session: AsyncSession,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        user_permissions: set[str] | None = None,
    ) -> MemoryItem:
        """Soft-delete memory item and evict vector index."""
        perms = user_permissions or set()
        require_memory_permission(perms, PERM_MEMORY_DELETE)

        item = await self.deletion_service.delete_memory(
            db_session=db_session,
            memory_id=memory_id,
            organization_id=organization_id,
            user_id=user_id,
            user_permissions=perms,
        )

        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="memory.deleted",
                resource_type="memory_item",
                resource_id=str(memory_id),
            )
        )
        await db_session.commit()
        await db_session.refresh(item)
        self.instrumentation.record_memory_delete()
        return item

    async def update_memory(
        self,
        db_session: AsyncSession,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
        request: MemoryItemUpdateRequest,
        user_id: uuid.UUID | None = None,
        user_permissions: set[str] | None = None,
    ) -> MemoryItem:
        """Update existing memory item and record version snapshot."""
        perms = user_permissions or set()
        require_memory_permission(perms, PERM_MEMORY_UPDATE)

        item = await self.metadata_store.get_by_id(
            db_session=db_session,
            memory_id=memory_id,
            organization_id=organization_id,
        )
        if not item:
            raise MemoryNotFoundError(memory_id)

        MemoryAccessPolicy.authorize_read(
            memory_item=item,
            caller_org_id=organization_id,
            caller_user_id=user_id,
            user_permissions=perms,
        )

        if request.content is not None:
            MemoryPrivacyFilter.enforce(request.content)
            item.content = request.content
            item.content_hash = compute_content_hash(request.content)

        if request.summary is not None:
            item.summary = request.summary
        if request.importance is not None:
            item.importance = request.importance
        if request.confidence is not None:
            item.confidence = request.confidence
        if request.visibility is not None:
            item.visibility = request.visibility.value
        if request.privacy_level is not None:
            MemoryAccessPolicy.authorize_write(request.privacy_level, perms)
            item.privacy_level = request.privacy_level.value

        item.version += 1
        item.updated_at = datetime.now(UTC)

        # Record version snapshot
        version = MemoryVersion(
            organization_id=organization_id,
            memory_id=item.id,
            version=item.version,
            content=item.content,
            summary=item.summary,
            importance=item.importance,
            confidence=item.confidence,
        )
        db_session.add(version)
        await db_session.flush()

        # Update vector index
        await self.vector_store.index_memory(item)

        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="memory.updated",
                resource_type="memory_item",
                resource_id=str(memory_id),
            )
        )
        await db_session.commit()
        await db_session.refresh(item)
        return item
