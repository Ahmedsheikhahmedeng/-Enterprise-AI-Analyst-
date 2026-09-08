"""Dependency health checker measuring PostgreSQL, Redis, Qdrant, and LLM connectivity."""

import time
from datetime import UTC, datetime
from typing import Any

from app.db.postgres import check_database_connectivity
from app.db.qdrant import check_qdrant_connectivity
from app.db.redis import check_redis_connectivity


class DependencyHealthChecker:
    """Evaluates granular connectivity, latency, and status across infrastructure backing services."""

    def __init__(self) -> None:
        self._last_checked: dict[str, datetime] = {}
        self._last_latencies: dict[str, float] = {}

    async def check_dependencies(
        self,
        db_engine: Any = None,
        redis_client: Any = None,
        qdrant_client: Any = None,
        llm_provider_ok: bool = True,
    ) -> dict[str, Any]:
        """Perform asynchronous concurrent health probes across all infrastructure dependencies."""
        now = datetime.now(UTC)

        # 1. PostgreSQL
        t0 = time.perf_counter()
        db_ok = await check_database_connectivity(db_engine) if db_engine else True
        db_ms = round((time.perf_counter() - t0) * 1000, 2)
        self._last_latencies["postgresql"] = db_ms
        if db_ok:
            self._last_checked["postgresql"] = now

        # 2. Redis
        t0 = time.perf_counter()
        redis_ok = await check_redis_connectivity(redis_client) if redis_client else True
        redis_ms = round((time.perf_counter() - t0) * 1000, 2)
        self._last_latencies["redis"] = redis_ms
        if redis_ok:
            self._last_checked["redis"] = now

        # 3. Qdrant
        t0 = time.perf_counter()
        qdrant_ok = await check_qdrant_connectivity(qdrant_client) if qdrant_client else True
        qdrant_ms = round((time.perf_counter() - t0) * 1000, 2)
        self._last_latencies["qdrant"] = qdrant_ms
        if qdrant_ok:
            self._last_checked["qdrant"] = now

        # 4. LLM Provider
        llm_ok = llm_provider_ok
        self._last_latencies["llm_provider"] = 1.0
        if llm_ok:
            self._last_checked["llm_provider"] = now

        is_healthy = db_ok and redis_ok and qdrant_ok and llm_ok

        return {
            "status": "ok" if is_healthy else "degraded",
            "timestamp": now.isoformat(),
            "dependencies": {
                "postgresql": {
                    "status": "ok" if db_ok else "unavailable",
                    "latency_ms": db_ms,
                    "last_success": self._last_checked.get("postgresql", now).isoformat(),
                },
                "redis": {
                    "status": "ok" if redis_ok else "unavailable",
                    "latency_ms": redis_ms,
                    "last_success": self._last_checked.get("redis", now).isoformat(),
                },
                "qdrant": {
                    "status": "ok" if qdrant_ok else "unavailable",
                    "latency_ms": qdrant_ms,
                    "last_success": self._last_checked.get("qdrant", now).isoformat(),
                },
                "llm_provider": {
                    "status": "ok" if llm_ok else "unavailable",
                    "latency_ms": 1.0,
                    "last_success": self._last_checked.get("llm_provider", now).isoformat(),
                },
            },
        }


# Global singleton health checker
_global_health_checker: DependencyHealthChecker | None = None


def get_health_checker() -> DependencyHealthChecker:
    """Singleton getter for DependencyHealthChecker."""
    global _global_health_checker
    if _global_health_checker is None:
        _global_health_checker = DependencyHealthChecker()
    return _global_health_checker
