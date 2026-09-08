"""Redis response caching infrastructure for Enterprise LLM Gateway."""

import hashlib
import json
import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.llm_gateway.domain.models import LLMMessage, LLMResponsePayload

logger = logging.getLogger(__name__)


class LLMCache:
    """Redis-backed tenant-isolated cache for deterministic and non-sensitive LLM responses."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client

    async def _get_client(self) -> Any:
        if self._redis is not None:
            return self._redis
        try:
            import redis.asyncio as aioredis

            settings = get_settings()
            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            self._redis = aioredis.from_url(redis_url, decode_responses=True)
            return self._redis
        except Exception as exc:
            logger.warning("Redis client initialization failed: %s", exc)
            return None

    @staticmethod
    def compute_hash(data: str) -> str:
        """Compute SHA-256 hex digest of string input."""
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @classmethod
    def compute_messages_hash(cls, messages: list[LLMMessage]) -> str:
        """Compute deterministic hash of prompt messages."""
        serialized = json.dumps(
            [{"role": m.role.value, "content": m.content} for m in messages],
            sort_keys=True,
        )
        return cls.compute_hash(serialized)

    @classmethod
    def build_cache_key(
        cls,
        *,
        organization_id: UUID,
        model: str,
        prompt_hash: str,
        input_hash: str,
        policy_version: str = "v1",
    ) -> str:
        """Build canonical cache key: llm:{org_id}:{model}:{prompt_hash}:{input_hash}:{policy_version}."""
        return f"llm:{str(organization_id)}:{model.lower()}:{prompt_hash}:{input_hash}:{policy_version}"

    build_key = build_cache_key

    async def get(self, cache_key: str) -> LLMResponsePayload | None:
        """Retrieve and deserialize cached LLM response."""
        client = await self._get_client()
        if client is None:
            return None
        try:
            raw = await client.get(cache_key)
            if not raw:
                return None
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None

            return LLMResponsePayload(
                content=str(data.get("content", "")),
                provider=str(data.get("provider", "cached")),
                model=str(data.get("model", "")),
                model_version=str(data.get("model_version", "latest")),
                input_tokens=int(data.get("input_tokens", 0)),
                output_tokens=int(data.get("output_tokens", 0)),
                total_tokens=int(data.get("total_tokens", 0)),
                estimated_cost=Decimal(str(data.get("estimated_cost", "0.0"))),
                latency_ms=int(data.get("latency_ms", 0)),
                finish_reason=str(data.get("finish_reason", "stop")),
                fallback_used=bool(data.get("fallback_used", False)),
                fallback_history=list(data.get("fallback_history", [])),
                cache_hit=True,
                request_id=str(data.get("request_id", "")),
                parsed_json=data.get("parsed_json"),
                metadata=data.get("metadata", {}),
            )
        except Exception as exc:
            logger.warning("Error reading from LLM cache: %s", exc)
            return None

    async def set(
        self,
        cache_key: str,
        response: LLMResponsePayload,
        ttl_seconds: int = 3600,
    ) -> None:
        """Store serialized LLM response in Redis with expiration."""
        client = await self._get_client()
        if client is None:
            return
        try:
            payload_dict = {
                "content": response.content,
                "provider": response.provider,
                "model": response.model,
                "model_version": response.model_version,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
                "estimated_cost": str(response.estimated_cost),
                "latency_ms": response.latency_ms,
                "finish_reason": response.finish_reason,
                "fallback_used": response.fallback_used,
                "fallback_history": response.fallback_history,
                "request_id": response.request_id,
                "parsed_json": response.parsed_json,
                "metadata": response.metadata,
            }
            await client.setex(cache_key, ttl_seconds, json.dumps(payload_dict))
        except Exception as exc:
            logger.warning("Error writing to LLM cache: %s", exc)

    async def invalidate_tenant(self, organization_id: UUID) -> int:
        """Purge all cached responses for a specific tenant."""
        client = await self._get_client()
        if client is None:
            return 0
        try:
            pattern = f"llm:{str(organization_id)}:*"
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    deleted += await client.delete(*keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as exc:
            logger.warning("Error invalidating tenant LLM cache: %s", exc)
            return 0
