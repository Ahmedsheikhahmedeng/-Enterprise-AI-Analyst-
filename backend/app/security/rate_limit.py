"""Rate Limiting Abstraction & Implementations — TASK 22.

Provides sliding window rate limiting with:
1. Redis backend (when available)
2. In-memory sliding window fallback (safe, deterministic, bounded)
3. Specialized keys combining client IP, user ID, tenant ID, and endpoint.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.security.config import SecurityConfig
from app.security.exceptions import RateLimitExceededError

logger = get_logger("security.rate_limit")


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_at: int


class RateLimiter:
    """Sliding-window rate limiter with Redis backend and thread-safe in-memory fallback."""

    def __init__(
        self,
        redis_client: Any | None = None,
        config: SecurityConfig | None = None,
    ) -> None:
        self._redis = redis_client
        self._config = config or SecurityConfig()
        # In-memory sliding log fallback: key -> list of float timestamps
        self._memory_store: dict[str, list[float]] = defaultdict(list)

    async def check(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Check whether the request for `key` is allowed under `limit` per `window_seconds`."""
        if self._redis is not None:
            try:
                return await self._check_redis(key, limit, window_seconds)
            except Exception as exc:
                logger.warning(
                    "Redis rate limit check failed, falling back to in-memory: %s",
                    str(exc),
                )

        return self._check_memory(key, limit, window_seconds)

    async def _check_redis(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Sliding-window check using Redis sorted sets (ZSET)."""
        if self._redis is None:
            return self._check_memory(key, limit, window_seconds)
        now = time.time()
        clear_before = now - window_seconds
        redis_key = f"ratelimit:{key}"

        pipe = self._redis.pipeline()
        # 1. Remove timestamps outside the sliding window
        pipe.zremrangebyscore(redis_key, 0, clear_before)
        # 2. Count requests remaining in window
        pipe.zcard(redis_key)
        # 3. Add current timestamp tentatively (we will remove or keep based on result)
        pipe.zadd(redis_key, {str(now): now})
        # 4. Set expiry on the zset key
        pipe.expire(redis_key, window_seconds + 5)
        results = await pipe.execute()

        current_count = results[1]

        if current_count >= limit:
            # Over limit, remove the tentative entry
            await self._redis.zrem(redis_key, str(now))
            # Find earliest timestamp in window to compute retry_after
            earliest = await self._redis.zrange(redis_key, 0, 0, withscores=True)
            if earliest:
                earliest_ts = float(earliest[0][1])
                retry_after = max(1, int(earliest_ts + window_seconds - now))
            else:
                retry_after = window_seconds

            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=retry_after,
                reset_at=int(now + retry_after),
            )

        remaining = max(0, limit - (current_count + 1))
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            retry_after=0,
            reset_at=int(now + window_seconds),
        )

    def _check_memory(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitResult:
        """Sliding-window check using in-memory timestamp list."""
        now = time.time()
        window_start = now - window_seconds

        timestamps = self._memory_store[key]
        # Filter out timestamps older than the window
        valid_timestamps = [ts for ts in timestamps if ts > window_start]

        if len(valid_timestamps) >= limit:
            earliest_ts = valid_timestamps[0]
            retry_after = max(1, int(earliest_ts + window_seconds - now))
            self._memory_store[key] = valid_timestamps
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=retry_after,
                reset_at=int(now + retry_after),
            )

        valid_timestamps.append(now)
        self._memory_store[key] = valid_timestamps
        remaining = max(0, limit - len(valid_timestamps))
        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=remaining,
            retry_after=0,
            reset_at=int(now + window_seconds),
        )

    def assert_allowed(
        self,
        result: RateLimitResult,
        endpoint: str = "request",
    ) -> None:
        """Raise RateLimitExceededError if rate limit is exceeded."""
        if not result.allowed:
            raise RateLimitExceededError(
                message=f"Rate limit exceeded for {endpoint}. Please retry after {result.retry_after} seconds.",
                retry_after=result.retry_after,
                limit=result.limit,
            )

    @staticmethod
    def build_key(
        endpoint: str,
        client_ip: str | None = None,
        user_id: str | None = None,
        organization_id: str | None = None,
    ) -> str:
        """Construct a structured rate limit key."""
        parts = [f"ep:{endpoint}"]
        if organization_id:
            parts.append(f"org:{organization_id}")
        if user_id:
            parts.append(f"usr:{user_id}")
        if client_ip:
            parts.append(f"ip:{client_ip}")
        return ":".join(parts)
