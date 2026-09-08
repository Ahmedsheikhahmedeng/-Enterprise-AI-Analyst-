"""High-level Semantic Discovery service coordinating Hybrid Search and Redis caching."""

import hashlib
import json
import uuid

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.semantic.application.normalizer import SemanticTextNormalizer
from app.semantic.domain.models import SemanticSearchResultItem
from app.semantic.infrastructure.search import HybridSemanticSearchEngine

CACHE_PREFIX = "semantic"
DEFAULT_CACHE_TTL = 300  # 5 minutes


class SemanticSearchService:
    """Coordinates cached hybrid discovery across the business semantic layer."""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Redis | None = None,
    ) -> None:
        self.session = session
        self.redis_client = redis_client
        self.engine = HybridSemanticSearchEngine(session)

    def _build_cache_key(
        self,
        organization_id: uuid.UUID,
        query: str,
        version: int = 1,
    ) -> str:
        norm_query = SemanticTextNormalizer.normalize(query)
        q_hash = hashlib.sha256(norm_query.encode("utf-8")).hexdigest()[:16]
        return f"{CACHE_PREFIX}:{organization_id}:{q_hash}:v{version}"

    async def search(
        self,
        query: str,
        organization_id: uuid.UUID,
        limit: int = 10,
        object_types: list[str] | None = None,
        only_published: bool = True,
    ) -> list[SemanticSearchResultItem]:
        """Search semantic catalog with tenant-isolated caching."""
        cache_key = self._build_cache_key(organization_id, query)

        # 1. Try Redis Cache
        if self.redis_client is not None:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    raw_items = json.loads(cached_data)
                    return [SemanticSearchResultItem.model_validate(item) for item in raw_items]
            except Exception:
                pass

        # 2. Execute Hybrid Search
        results = await self.engine.search(
            query=query,
            organization_id=organization_id,
            limit=limit,
            object_types=object_types,
            only_published=only_published,
        )

        # 3. Cache results
        if self.redis_client is not None and results:
            try:
                payload = json.dumps([item.model_dump(mode="json") for item in results])
                await self.redis_client.setex(cache_key, DEFAULT_CACHE_TTL, payload)
            except Exception:
                pass

        return results

    async def invalidate_tenant_cache(self, organization_id: uuid.UUID) -> None:
        """Purge all cached search results for an organization."""
        if self.redis_client is not None:
            try:
                pattern = f"{CACHE_PREFIX}:{organization_id}:*"
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception:
                pass
