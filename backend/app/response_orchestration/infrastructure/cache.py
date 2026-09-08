"""Redis caching layer for response orchestration ensuring strict tenant isolation."""

import hashlib
import json
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


class OrchestrationCache:
    """Provides semantic and query caching scoped by organization ID."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl = ttl_seconds
        self._memory_store: dict[str, str] = {}

    def _make_key(
        self,
        organization_id: uuid.UUID,
        mode: str,
        query: str,
        semantic_version: str = "v1",
    ) -> str:
        q_hash = hashlib.sha256(query.strip().lower().encode("utf-8")).hexdigest()
        return f"orch:{organization_id}:{mode.lower()}:{q_hash}:{semantic_version}"

    async def get(
        self,
        organization_id: uuid.UUID,
        mode: str,
        query: str,
        semantic_version: str = "v1",
    ) -> dict[str, Any] | None:
        """Retrieve cached response if available."""
        key = self._make_key(organization_id, mode, query, semantic_version)
        val = self._memory_store.get(key)
        if val:
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    return parsed
                return None
            except Exception:
                return None
        return None

    async def set(
        self,
        organization_id: uuid.UUID,
        mode: str,
        query: str,
        data: dict[str, Any],
        semantic_version: str = "v1",
    ) -> None:
        """Store response in cache."""
        key = self._make_key(organization_id, mode, query, semantic_version)
        try:
            self._memory_store[key] = json.dumps(data)
        except Exception as exc:
            logger.debug("Failed to set orchestration cache: %s", exc)
