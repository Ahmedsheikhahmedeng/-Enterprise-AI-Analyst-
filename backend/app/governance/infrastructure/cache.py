"""Cache utilities for governance policies and authorization gates."""

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class GovernanceCache:
    """Provides high-performance cache for active policies and authorization states."""

    def __init__(self) -> None:
        self._local_cache: dict[str, dict[str, Any]] = {}

    def _policy_key(self, organization_id: uuid.UUID) -> str:
        return f"governance:policy:{organization_id}"

    def _gate_key(self, approval_id: uuid.UUID) -> str:
        return f"governance:gate:{approval_id}"

    async def get_cached_policy(self, organization_id: uuid.UUID) -> dict[str, Any] | None:
        """Retrieve policy dict from Redis or fallback local cache."""
        key = self._policy_key(organization_id)
        return self._local_cache.get(key)

    async def set_cached_policy(
        self, organization_id: uuid.UUID, policy_data: dict[str, Any], ttl_seconds: int = 3600
    ) -> None:
        """Store policy dict in cache."""
        key = self._policy_key(organization_id)
        self._local_cache[key] = policy_data

    async def invalidate_policy(self, organization_id: uuid.UUID) -> None:
        """Invalidate cached policy upon update."""
        key = self._policy_key(organization_id)
        self._local_cache.pop(key, None)


_cache_instance: GovernanceCache | None = None


def get_governance_cache() -> GovernanceCache:
    """Singleton getter for governance cache."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = GovernanceCache()
    return _cache_instance
