"""Enterprise Pre-Execution Gate and domain governance orchestrator."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from app.governance.application.approval_service import ApprovalService
from app.governance.application.decision_service import (
    compute_action_hash,
    compute_resource_hash,
)
from app.governance.application.policy_service import PolicyService
from app.governance.application.risk_service import RiskService
from app.governance.domain.enums import ApprovalStatus, ApprovalType
from app.governance.domain.errors import (
    ApprovalExpiredError,
    ApprovalRevokedError,
    PreExecutionBlockedError,
    TOCTOUMismatchError,
)
from app.governance.domain.models import ApprovalRequest
from app.governance.infrastructure.repository import GovernanceRepository
from app.observability.instrumentation.governance import (
    AUDIT_ACTION_BLOCKED_BY_GOVERNANCE,
    get_governance_instrumentation,
)

logger = logging.getLogger(__name__)


class GovernanceService:
    """Pre-execution authorization gate and cross-domain enterprise governance controller."""

    def __init__(
        self,
        repository: GovernanceRepository,
        approval_service: ApprovalService,
        risk_service: RiskService,
        policy_service: PolicyService,
    ) -> None:
        self.repo = repository
        self.approval_service = approval_service
        self.risk_service = risk_service
        self.policy_service = policy_service
        self.instrumentation = get_governance_instrumentation()

    async def verify_pre_execution_gate(
        self,
        approval_id: uuid.UUID,
        organization_id: uuid.UUID,
        current_action_payload: Any,
        resource_type: str,
        resource_id: str | None = None,
    ) -> bool:
        """Enforce strict server-side pre-execution verification before executing a sensitive action.

        Verifies:
        1. Tenant isolation (request belongs to organization_id).
        2. Status is APPROVED.
        3. Expiration window (not expired).
        4. Cryptographic TOCTOU Protection: current action payload and resource match the approved hashes.
        """
        request: ApprovalRequest = await self.approval_service.get_request(
            organization_id=organization_id,
            request_id=approval_id,
        )

        now = datetime.now(UTC)

        # 1. Status Verification
        if request.status == ApprovalStatus.REVOKED:
            self.instrumentation.record_action_blocked(
                request.request_type.value, request.risk_level.value
            )
            raise ApprovalRevokedError(f"Approval {approval_id} was revoked prior to execution")

        if request.status != ApprovalStatus.APPROVED:
            self.instrumentation.record_action_blocked(
                request.request_type.value, request.risk_level.value
            )
            logger.warning(
                "Action blocked by governance gate: not approved",
                extra={
                    "event": AUDIT_ACTION_BLOCKED_BY_GOVERNANCE,
                    "approval_id": str(approval_id),
                    "status": request.status.value,
                },
            )
            raise PreExecutionBlockedError(
                f"Action requires formal approval. Current status is {request.status.value}"
            )

        # 2. Expiration Verification
        if request.expires_at <= now:
            self.instrumentation.record_action_blocked(
                request.request_type.value, request.risk_level.value
            )
            raise ApprovalExpiredError(
                f"Approval request {approval_id} expired at {request.expires_at}"
            )

        # 3. Cryptographic TOCTOU Check: Action Hash
        current_action_hash = compute_action_hash(current_action_payload)
        if request.action_hash and current_action_hash != request.action_hash:
            self.instrumentation.record_action_blocked(
                request.request_type.value, request.risk_level.value
            )
            logger.error(
                "TOCTOU mismatch detected: action payload changed after approval",
                extra={
                    "event": AUDIT_ACTION_BLOCKED_BY_GOVERNANCE,
                    "approval_id": str(approval_id),
                    "approved_hash": request.action_hash,
                    "current_hash": current_action_hash,
                },
            )
            raise TOCTOUMismatchError(
                "Action execution aborted: parameters were modified after approval was granted (TOCTOU violation)"
            )

        # 4. Cryptographic TOCTOU Check: Resource Hash
        current_resource_hash = compute_resource_hash(resource_type, resource_id)
        if request.resource_hash and current_resource_hash != request.resource_hash:
            self.instrumentation.record_action_blocked(
                request.request_type.value, request.risk_level.value
            )
            raise TOCTOUMismatchError(
                "Action execution aborted: target resource was modified after approval was granted"
            )

        return True

    async def evaluate_and_govern_action(
        self,
        organization_id: uuid.UUID,
        requester_id: uuid.UUID,
        request_type: ApprovalType,
        resource_type: str,
        resource_id: str | None,
        action_payload: Any,
        risk_factors: dict[str, Any] | None = None,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Unified entrypoint for any subsystem requiring governance validation before execution."""
        return await self.approval_service.create_approval_request(
            organization_id=organization_id,
            requester_id=requester_id,
            request_type=request_type,
            resource_type=resource_type,
            resource_id=resource_id,
            action_payload=action_payload,
            reason=reason,
            context=context,
            risk_factors=risk_factors,
        )
