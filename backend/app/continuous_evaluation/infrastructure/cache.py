"""In-memory caching layer for evaluation baselines and scorecards."""

import time
from typing import Any


class EvaluationCache:
    """Fast cache for baseline metrics, scorecards, and calibration results."""

    def __init__(self, default_ttl_seconds: int = 3600) -> None:
        self.default_ttl = default_ttl_seconds
        self._cache: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Retrieves cached item if not expired."""
        if key not in self._cache:
            return None
        expires_at, value = self._cache[key]
        if time.time() > expires_at:
            del self._cache[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Stores item with specified or default TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._cache[key] = (time.time() + ttl, value)

    def invalidate(self, key: str) -> None:
        """Removes an item from cache."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clears all cached entries."""
        self._cache.clear()
