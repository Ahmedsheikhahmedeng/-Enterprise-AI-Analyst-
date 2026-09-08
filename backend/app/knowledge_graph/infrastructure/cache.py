"""Tenant-scoped Redis cache for Knowledge Graph queries and traversals."""

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

GRAPH_CACHE_PREFIX = "graph"
DEFAULT_GRAPH_CACHE_TTL = 300  # 5 minutes


class KnowledgeGraphCache:
    """Manages Redis caching of graph query and path resolution results."""

    def __init__(
        self,
        redis_client: Redis | None = None,
        ttl_seconds: int = DEFAULT_GRAPH_CACHE_TTL,
    ) -> None:
        self.redis = redis_client
        self.ttl = ttl_seconds

    @staticmethod
    def build_cache_key(
        organization_id: UUID,
        query_identifier: str,
        graph_version: int,
    ) -> str:
        """Construct deterministic cache key: graph:{org_id}:{query_hash}:{version}."""
        q_hash = hashlib.sha256(query_identifier.encode("utf-8")).hexdigest()[:16]
        return f"{GRAPH_CACHE_PREFIX}:{organization_id}:{q_hash}:{graph_version}"

    async def get(
        self,
        organization_id: UUID,
        query_identifier: str,
        graph_version: int,
    ) -> dict[str, Any] | None:
        """Fetch cached graph result if available."""
        if not self.redis:
            return None
        key = self.build_cache_key(organization_id, query_identifier, graph_version)
        try:
            raw = await self.redis.get(key)
            if raw:
                parsed: Any = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except Exception as exc:
            logger.debug("Knowledge graph cache get error: %s", exc)
        return None

    async def set(
        self,
        organization_id: UUID,
        query_identifier: str,
        graph_version: int,
        data: dict[str, Any],
    ) -> None:
        """Store graph result with TTL."""
        if not self.redis:
            return
        key = self.build_cache_key(organization_id, query_identifier, graph_version)
        try:
            await self.redis.set(key, json.dumps(data), ex=self.ttl)
        except Exception as exc:
            logger.debug("Knowledge graph cache set error: %s", exc)

    async def invalidate_tenant(self, organization_id: UUID) -> None:
        """Invalidate all cached graph queries for a specific tenant organization."""
        if not self.redis:
            return
        try:
            pattern = f"{GRAPH_CACHE_PREFIX}:{organization_id}:*"
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            logger.debug("Knowledge graph cache invalidation error: %s", exc)
