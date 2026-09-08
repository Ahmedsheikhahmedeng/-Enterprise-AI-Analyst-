"""Embedding caching layer abstraction and implementations."""

import json
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


def build_embedding_cache_key(
    provider: str,
    model: str,
    version: str,
    input_hash: str,
) -> str:
    """Build a namespaced Redis/cache key without exposing raw chunk text.

    Format: embedding:{provider}:{model}:{version}:{hash}
    """
    clean_provider = provider.lower().strip()
    clean_model = model.lower().strip()
    clean_version = version.strip()
    return f"embedding:{clean_provider}:{clean_model}:{clean_version}:{input_hash}"


@runtime_checkable
class EmbeddingCache(Protocol):
    """Protocol for embedding vector caches."""

    async def get(self, key: str) -> list[float] | None:
        """Retrieve a cached vector by key, or None if miss."""
        ...

    async def set(
        self,
        key: str,
        vector: list[float],
        ttl_seconds: int | None = None,
    ) -> None:
        """Store a vector under the key with an optional TTL."""
        ...

    async def get_many(self, keys: list[str]) -> list[list[float] | None]:
        """Batch retrieve vectors by keys."""
        ...

    async def set_many(
        self,
        items: list[tuple[str, list[float]]],
        ttl_seconds: int | None = None,
    ) -> None:
        """Batch store vectors with an optional TTL."""
        ...


class NoopEmbeddingCache:
    """Cache implementation that performs no caching (always misses)."""

    async def get(self, key: str) -> list[float] | None:
        return None

    async def set(
        self,
        key: str,
        vector: list[float],
        ttl_seconds: int | None = None,
    ) -> None:
        pass

    async def get_many(self, keys: list[str]) -> list[list[float] | None]:
        return [None] * len(keys)

    async def set_many(
        self,
        items: list[tuple[str, list[float]]],
        ttl_seconds: int | None = None,
    ) -> None:
        pass


class InMemoryEmbeddingCache:
    """Thread-safe in-memory cache for unit tests and local execution."""

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = {}

    async def get(self, key: str) -> list[float] | None:
        return self._store.get(key)

    async def set(
        self,
        key: str,
        vector: list[float],
        ttl_seconds: int | None = None,
    ) -> None:
        self._store[key] = list(vector)

    async def get_many(self, keys: list[str]) -> list[list[float] | None]:
        return [self._store.get(k) for k in keys]

    async def set_many(
        self,
        items: list[tuple[str, list[float]]],
        ttl_seconds: int | None = None,
    ) -> None:
        for key, vector in items:
            self._store[key] = list(vector)

    def clear(self) -> None:
        self._store.clear()


class RedisEmbeddingCache:
    """Redis-backed vector cache using serialized JSON arrays.

    Safely handles Redis connection drops by failing open (treating errors as cache misses)
    without interrupting the embedding service pipeline.
    """

    def __init__(self, redis_client: Any, default_ttl: int = 86400 * 7) -> None:
        self.redis: Any = redis_client
        self.default_ttl = default_ttl

    async def get(self, key: str) -> list[float] | None:
        try:
            val = await self.redis.get(key)
            if val is not None:
                if isinstance(val, (bytes, bytearray)):
                    val = val.decode("utf-8")
                raw_list = json.loads(val)
                return [float(x) for x in raw_list]
        except Exception as exc:
            logger.warning(f"Embedding cache read failed: {exc}")
        return None

    async def set(
        self,
        key: str,
        vector: list[float],
        ttl_seconds: int | None = None,
    ) -> None:
        ttl = ttl_seconds or self.default_ttl
        try:
            payload = json.dumps(vector)
            await self.redis.set(key, payload, ex=ttl)
        except Exception as exc:
            logger.warning(f"Embedding cache write failed: {exc}")

    async def get_many(self, keys: list[str]) -> list[list[float] | None]:
        if not keys:
            return []
        try:
            values = await self.redis.mget(keys)
            result: list[list[float] | None] = []
            for val in values:
                if val is not None:
                    if isinstance(val, (bytes, bytearray)):
                        val = val.decode("utf-8")
                    result.append([float(x) for x in json.loads(val)])
                else:
                    result.append(None)
            return result
        except Exception as exc:
            logger.warning(f"Embedding cache mget failed: {exc}")
            return [None] * len(keys)

    async def set_many(
        self,
        items: list[tuple[str, list[float]]],
        ttl_seconds: int | None = None,
    ) -> None:
        if not items:
            return
        ttl = ttl_seconds or self.default_ttl
        try:
            pipe = self.redis.pipeline()
            for key, vector in items:
                pipe.set(key, json.dumps(vector), ex=ttl)
            await pipe.execute()
        except Exception as exc:
            logger.warning(f"Embedding cache mset failed: {exc}")
