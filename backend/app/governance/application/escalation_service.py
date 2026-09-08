"""Escalation and approval timeout management service."""

import logging
from datetime import UTC, datetime

from app.governance.domain.enums import ApprovalStatus
from app.governance.domain.models import ApprovalRequest
from app.governance.infrastructure.repository import GovernanceRepository
from app.observability.instrumentation.governance import (
    AUDIT_APPROVAL_EXPIRED,
    get_governance_instrumentation,
)

logger = logging.getLogger(__name__)


class EscalationService:
    """Detects timed-out approval requests, expires them, and routes escalations."""

    def __init__(self, repository: GovernanceRepository) -> None:
        self.repo = repository
        self.instrumentation = get_governance_instrumentation()

    async def process_expired_requests(self, now: datetime | None = None) -> list[ApprovalRequest]:
        """Find pending or in-review requests that exceeded their expiration deadline and mark EXPIRED."""
        current_time = now or datetime.now(UTC)
        expired_models = await self.repo.get_expired_pending_requests(current_time)
        processed: list[ApprovalRequest] = []

        for req in expired_models:
            req.status = ApprovalStatus.EXPIRED.value
            req.updated_at = current_time
            self.instrumentation.record_approval_expired(
                request_type=req.request_type,
                risk_level=req.risk_level,
            )
            logger.info(
                "Approval request expired",
                extra={
                    "event": AUDIT_APPROVAL_EXPIRED,
                    "approval_id": str(req.id),
                    "organization_id": str(req.organization_id),
                    "request_type": req.request_type,
                    "risk_level": req.risk_level,
                },
            )
            processed.append(
                ApprovalRequest(
                    id=req.id,
                    organization_id=req.organization_id,
                    request_type=req.request_type,  # type: ignore[arg-type]
                    requester_id=req.requester_id,
                    resource_type=req.resource_type,
                    resource_id=req.resource_id,
                    risk_level=req.risk_level,  # type: ignore[arg-type]
                    risk_score=req.risk_score,
                    status=ApprovalStatus.EXPIRED,
                    reason=req.reason,
                    context=req.context or {},
                    action_hash=req.action_hash,
                    resource_hash=req.resource_hash,
                    policy_version=req.policy_version,
                    expires_at=req.expires_at,
                    created_at=req.created_at,
                    updated_at=req.updated_at,
                )
            )

        if expired_models:
            await self.repo.session.flush()

        return processed
