"""Cache policy evaluation and key orchestration service."""

from uuid import UUID

from app.llm_gateway.domain.enums import DataSensitivity, LLMTaskType
from app.llm_gateway.domain.models import (
    LLMRequestPayload,
    LLMResponsePayload,
    TenantLLMPolicy,
)
from app.llm_gateway.infrastructure.cache import LLMCache


class CacheService:
    """Evaluates task cacheability and interacts with tenant-isolated LLMCache."""

    CACHEABLE_TASK_TYPES = {
        LLMTaskType.EVALUATION_JUDGE,
        LLMTaskType.QUERY_REWRITE,
        LLMTaskType.SEMANTIC_REASONING,
        LLMTaskType.GRAPH_REASONING,
        LLMTaskType.REPORT_GENERATION,
        LLMTaskType.RAG_ANSWER,
        LLMTaskType.SQL_GENERATION,
    }

    def __init__(self, cache: LLMCache | None = None) -> None:
        self.cache = cache or LLMCache()

    def is_cacheable(
        self,
        payload: LLMRequestPayload,
        policy: TenantLLMPolicy | None = None,
    ) -> bool:
        """Evaluate if an LLM invocation satisfies safety criteria for response caching."""
        # 1. Tenant policy prohibition
        if policy and not policy.caching_allowed:
            return False

        # 2. Temperature safety: non-deterministic responses should not be cached
        if payload.temperature > 0.0:
            return False

        # 3. Sensitivity safety: Restricted or highly sensitive data must bypass cache
        if payload.data_sensitivity in (DataSensitivity.RESTRICTED, DataSensitivity.SENSITIVE):
            return False

        # 4. Task type safety check
        return payload.task_type in self.CACHEABLE_TASK_TYPES

    def build_key(
        self,
        organization_id: UUID,
        model_name: str,
        payload: LLMRequestPayload,
        policy_version: str = "v1",
    ) -> str:
        """Construct canonical cache key."""
        prompt_hash = (
            payload.prompt_metadata.template_hash
            if payload.prompt_metadata and payload.prompt_metadata.template_hash
            else self.cache.compute_hash(payload.task_type.value)
        )
        input_hash = self.cache.compute_messages_hash(payload.messages)

        return self.cache.build_key(
            organization_id=organization_id,
            model=model_name,
            prompt_hash=prompt_hash,
            input_hash=input_hash,
            policy_version=policy_version,
        )

    async def get_cached_response(self, cache_key: str) -> LLMResponsePayload | None:
        return await self.cache.get(cache_key)

    async def store_response(
        self,
        cache_key: str,
        response: LLMResponsePayload,
        ttl_seconds: int = 3600,
    ) -> None:
        await self.cache.set(cache_key, response, ttl_seconds=ttl_seconds)
