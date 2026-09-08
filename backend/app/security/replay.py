"""Replay & Idempotency Protection — TASK 22.

Provides Idempotency-Key protection for sensitive mutation APIs:
- Fingerprints request method, path, and payload.
- Detects parameter tampering when the same key is reused with a different payload.
- Prevents double-invocation of expensive workflows (reports, evaluation runs).
- Supports Redis with deterministic in-memory fallback.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from app.core.logging import get_logger
from app.security.exceptions import ReplayViolationError

logger = get_logger("security.replay")


@dataclass
class IdempotencyRecord:
    key: str
    fingerprint: str
    user_id: str | None
    tenant_id: str | None
    endpoint: str
    status: str  # "IN_PROGRESS" or "COMPLETED"
    created_at: float
    response_data: dict[str, Any] | None = None


class IdempotencyManager:
    """Manages API idempotency keys and replay protection."""

    def __init__(self, redis_client: Any | None = None, default_ttl_seconds: int = 300) -> None:
        self._redis = redis_client
        self._default_ttl = default_ttl_seconds
        # In-memory store: composite_key -> (IdempotencyRecord, expires_at)
        self._memory_store: dict[str, tuple[IdempotencyRecord, float]] = {}

    @staticmethod
    def compute_fingerprint(method: str, path: str, body: bytes | str | None = None) -> str:
        """Generate a SHA-256 fingerprint from the request parameters."""
        h = hashlib.sha256()
        h.update(method.upper().encode("utf-8"))
        h.update(b":")
        h.update(path.encode("utf-8"))
        h.update(b":")
        if body:
            if isinstance(body, str):
                h.update(body.encode("utf-8"))
            else:
                h.update(body)
        return h.hexdigest()

    async def acquire_or_check(
        self,
        idempotency_key: str,
        fingerprint: str,
        endpoint: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> tuple[bool, IdempotencyRecord]:
        """Check or acquire an idempotency lock for the given key.

        Returns:
            (is_new_request, record)
            - If is_new_request is True: the key was newly acquired. Caller executes work.
            - If is_new_request is False: a previous matching request was found.
        Raises:
            ReplayViolationError if key is reused with a mismatched fingerprint.
        """
        ttl = ttl_seconds or self._default_ttl
        storage_key = f"idempotency:{tenant_id or 'global'}:{idempotency_key}"

        if self._redis is not None:
            try:
                return await self._acquire_redis(
                    storage_key, idempotency_key, fingerprint, endpoint, user_id, tenant_id, ttl
                )
            except Exception as exc:
                logger.warning(
                    "Redis idempotency acquisition failed, falling back to in-memory: %s",
                    str(exc),
                )

        return self._acquire_memory(
            storage_key, idempotency_key, fingerprint, endpoint, user_id, tenant_id, ttl
        )

    async def record_completion(
        self,
        idempotency_key: str,
        tenant_id: str | None,
        response_data: dict[str, Any] | None = None,
    ) -> None:
        """Mark the idempotent operation as completed and store response reference."""
        storage_key = f"idempotency:{tenant_id or 'global'}:{idempotency_key}"

        if self._redis is not None:
            try:
                raw = await self._redis.get(storage_key)
                if raw:
                    data = json.loads(raw)
                    data["status"] = "COMPLETED"
                    data["response_data"] = response_data
                    ttl = await self._redis.ttl(storage_key)
                    await self._redis.set(storage_key, json.dumps(data), ex=max(ttl, 60))
                return
            except Exception as exc:
                logger.warning("Redis completion record failed: %s", str(exc))

        if storage_key in self._memory_store:
            rec, exp = self._memory_store[storage_key]
            rec.status = "COMPLETED"
            rec.response_data = response_data
            self._memory_store[storage_key] = (rec, exp)

    async def _acquire_redis(
        self,
        storage_key: str,
        idempotency_key: str,
        fingerprint: str,
        endpoint: str,
        user_id: str | None,
        tenant_id: str | None,
        ttl: int,
    ) -> tuple[bool, IdempotencyRecord]:
        if self._redis is None:
            return self._acquire_memory(
                storage_key, idempotency_key, fingerprint, endpoint, user_id, tenant_id, ttl
            )
        raw = await self._redis.get(storage_key)
        now = time.time()

        if raw:
            data = json.loads(raw)
            if data["fingerprint"] != fingerprint:
                raise ReplayViolationError(
                    f"Idempotency key '{idempotency_key}' was previously used with a different request payload."
                )
            record = IdempotencyRecord(
                key=data["key"],
                fingerprint=data["fingerprint"],
                user_id=data.get("user_id"),
                tenant_id=data.get("tenant_id"),
                endpoint=data["endpoint"],
                status=data["status"],
                created_at=data["created_at"],
                response_data=data.get("response_data"),
            )
            return False, record

        new_record = IdempotencyRecord(
            key=idempotency_key,
            fingerprint=fingerprint,
            user_id=user_id,
            tenant_id=tenant_id,
            endpoint=endpoint,
            status="IN_PROGRESS",
            created_at=now,
        )
        await self._redis.set(storage_key, json.dumps(asdict(new_record)), ex=ttl)
        return True, new_record

    def _acquire_memory(
        self,
        storage_key: str,
        idempotency_key: str,
        fingerprint: str,
        endpoint: str,
        user_id: str | None,
        tenant_id: str | None,
        ttl: int,
    ) -> tuple[bool, IdempotencyRecord]:
        now = time.time()
        # Clean expired
        if storage_key in self._memory_store:
            rec, expires_at = self._memory_store[storage_key]
            if now > expires_at:
                del self._memory_store[storage_key]
            else:
                if rec.fingerprint != fingerprint:
                    raise ReplayViolationError(
                        f"Idempotency key '{idempotency_key}' was previously used with a different request payload."
                    )
                return False, rec

        new_record = IdempotencyRecord(
            key=idempotency_key,
            fingerprint=fingerprint,
            user_id=user_id,
            tenant_id=tenant_id,
            endpoint=endpoint,
            status="IN_PROGRESS",
            created_at=now,
        )
        self._memory_store[storage_key] = (new_record, now + ttl)
        return True, new_record
