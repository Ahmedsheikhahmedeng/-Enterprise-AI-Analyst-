"""Cryptographic hashing and immutable decision ledger service."""

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.governance.domain.enums import ApprovalStatus
from app.governance.domain.models import ApprovalDecision
from app.governance.infrastructure.repository import GovernanceRepository

logger = logging.getLogger(__name__)


def compute_action_hash(action_payload: Any) -> str:
    """Compute canonical deterministic SHA256 hash of an operation's inputs.

    Prevents Time-Of-Check to Time-Of-Use (TOCTOU) tampering.
    """
    if action_payload is None:
        return hashlib.sha256(b"").hexdigest()
    if isinstance(action_payload, str):
        canonical_str = action_payload.strip()
    else:
        try:
            canonical_str = json.dumps(action_payload, sort_keys=True, default=str)
        except Exception:
            canonical_str = str(action_payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def compute_resource_hash(resource_type: str, resource_id: str | None) -> str:
    """Compute cryptographic hash of target resource identifier."""
    raw = f"{resource_type}:{resource_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_decision_hash(
    request_id: uuid.UUID,
    decision: str,
    reviewer_ids: list[str],
    policy_version: int,
    risk_score: float,
    timestamp: datetime | None = None,
) -> str:
    """Compute cryptographic hash of a final governance resolution.

    Ensures zero silent mutation of historical decision records.
    """
    sorted_reviewers = ",".join(sorted(reviewer_ids))
    ts_str = timestamp.isoformat() if timestamp else ""
    raw = f"{request_id}:{decision}:{sorted_reviewers}:{policy_version}:{risk_score:.4f}:{ts_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DecisionService:
    """Manages creation and verification of immutable approval decision records."""

    def __init__(self, repository: GovernanceRepository) -> None:
        self.repo = repository

    async def record_decision(
        self,
        organization_id: uuid.UUID,
        request_id: uuid.UUID,
        decision: ApprovalStatus,
        reviewer_ids: list[str],
        policy_version: int,
        risk_score: float,
    ) -> ApprovalDecision:
        """Create and persist an immutable decision record with verification hash."""
        now = datetime.now(UTC)
        d_hash = compute_decision_hash(
            request_id=request_id,
            decision=decision.value,
            reviewer_ids=reviewer_ids,
            policy_version=policy_version,
            risk_score=risk_score,
            timestamp=now,
        )
        record = await self.repo.create_decision(
            organization_id=organization_id,
            request_id=request_id,
            decision=decision.value,
            reviewer_ids=reviewer_ids,
            policy_version=policy_version,
            risk_score=risk_score,
            decision_hash=d_hash,
        )
        return ApprovalDecision(
            id=record.id,
            request_id=record.request_id,
            organization_id=record.organization_id,
            decision=ApprovalStatus(record.decision),
            reviewer_ids=record.reviewer_ids,
            policy_version=record.policy_version,
            risk_score=record.risk_score,
            decision_hash=record.decision_hash,
            created_at=record.created_at,
        )

    async def get_decision(
        self, organization_id: uuid.UUID, request_id: uuid.UUID
    ) -> ApprovalDecision | None:
        """Retrieve decision record."""
        record = await self.repo.get_decision_by_request(organization_id, request_id)
        if not record:
            return None
        return ApprovalDecision(
            id=record.id,
            request_id=record.request_id,
            organization_id=record.organization_id,
            decision=ApprovalStatus(record.decision),
            reviewer_ids=record.reviewer_ids,
            policy_version=record.policy_version,
            risk_score=record.risk_score,
            decision_hash=record.decision_hash,
            created_at=record.created_at,
        )
