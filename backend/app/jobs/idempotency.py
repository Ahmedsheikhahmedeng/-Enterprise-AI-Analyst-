"""Idempotency management and canonical payload hashing for background jobs."""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.exceptions import JobIdempotencyConflictError
from app.jobs.models import Job


class JobIdempotencyManager:
    """Manages job deduplication and idempotency key guarantees."""

    @staticmethod
    def compute_payload_hash(payload: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 hash of payload using canonical JSON."""
        # Ensure canonical formatting: sorted keys, no whitespace around separators
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
            default=str,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def check_existing(
        db: Session,
        organization_id: uuid.UUID,
        idempotency_key: str,
        payload_hash: str,
    ) -> Job | None:
        """Check if a job with this idempotency key already exists for the organization.

        Returns:
            Existing Job if key and payload hash match.

        Raises:
            JobIdempotencyConflictError: If key matches but payload hash differs.
        """
        stmt = (
            select(Job)
            .where(
                Job.organization_id == organization_id,
                Job.idempotency_key == idempotency_key,
            )
            .limit(1)
        )
        existing = db.execute(stmt).scalar_one_or_none()

        if existing is None:
            return None

        if existing.deduplication_hash != payload_hash:
            raise JobIdempotencyConflictError(idempotency_key)

        return existing
