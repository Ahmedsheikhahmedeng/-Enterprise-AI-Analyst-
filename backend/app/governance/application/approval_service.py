"""Human-in-the-loop approval lifecycle, voting, and quorum engine."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from app.governance.application.decision_service import (
    DecisionService,
    compute_action_hash,
    compute_resource_hash,
)
from app.governance.application.policy_service import PolicyService
from app.governance.application.risk_service import RiskService
from app.governance.domain.enums import (
    ApprovalStatus,
    ApprovalType,
    RiskLevel,
    VoteDecision,
)
from app.governance.domain.errors import (
    ApprovalExpiredError,
    ApprovalNotFoundError,
    InvalidStateTransitionError,
    SelfApprovalError,
)
from app.governance.domain.models import (
    ApprovalComment,
    ApprovalQuorum,
    ApprovalRequest,
    ApprovalRequirement,
    ApprovalVote,
    RiskAssessment,
)
from app.governance.infrastructure.repository import GovernanceRepository
from app.observability.instrumentation.governance import (
    AUDIT_APPROVAL_APPROVED,
    AUDIT_APPROVAL_CANCELLED,
    AUDIT_APPROVAL_CHANGES_REQUESTED,
    AUDIT_APPROVAL_REJECTED,
    AUDIT_APPROVAL_REVOKED,
    AUDIT_APPROVAL_STARTED,
    AUDIT_RISK_ASSESSED,
    get_governance_instrumentation,
)

logger = logging.getLogger(__name__)


class ApprovalService:
    """Orchestrates approval request lifecycle, multi-approver voting, quorum, and revocation."""

    def __init__(
        self,
        repository: GovernanceRepository,
        risk_service: RiskService,
        policy_service: PolicyService,
        decision_service: DecisionService,
    ) -> None:
        self.repo = repository
        self.risk_service = risk_service
        self.policy_service = policy_service
        self.decision_service = decision_service
        self.instrumentation = get_governance_instrumentation()

    async def create_approval_request(
        self,
        organization_id: uuid.UUID,
        requester_id: uuid.UUID,
        request_type: ApprovalType | str,
        resource_type: str,
        resource_id: str | None,
        action_payload: Any = None,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
        risk_factors: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Evaluate risk, check organization policy, and instantiate an approval request.

        If policy allows automatic approval (e.g. LOW risk), it transitions immediately
        to APPROVED and seals an immutable decision record.
        """
        req_type = ApprovalType(request_type) if isinstance(request_type, str) else request_type
        ctx = context or {}
        factors = risk_factors or {}

        # 1. Deterministic Risk Assessment
        risk: RiskAssessment = self.risk_service.assess_risk(req_type, factors)
        self.instrumentation.record_risk_assessed(req_type.value, risk.risk_level.value)
        logger.info(
            "Governance risk assessed",
            extra={
                "event": AUDIT_RISK_ASSESSED,
                "request_type": req_type.value,
                "risk_level": risk.risk_level.value,
                "risk_score": risk.risk_score,
                "reasons": risk.reasons,
            },
        )

        # 2. Policy Engine Evaluation
        policy = await self.policy_service.get_active_policy(organization_id)
        requirement: ApprovalRequirement = self.policy_service.evaluate_requirement(
            policy=policy,
            risk=risk,
            request_type=req_type,
        )

        # 3. Cryptographic Hashes for TOCTOU and Audit
        action_hash = compute_action_hash(action_payload)
        resource_hash = compute_resource_hash(resource_type, resource_id)

        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=requirement.timeout_minutes)
        request_id = uuid.uuid4()

        # 4. Automatic Approval vs Human Review Gate
        status = ApprovalStatus.APPROVED if not requirement.required else ApprovalStatus.PENDING

        record = await self.repo.create_request(
            request_id=request_id,
            organization_id=organization_id,
            request_type=req_type.value,
            requester_id=requester_id,
            resource_type=resource_type,
            resource_id=resource_id,
            risk_level=risk.risk_level.value,
            risk_score=risk.risk_score,
            status=status.value,
            reason=reason,
            context=ctx,
            action_hash=action_hash,
            resource_hash=resource_hash,
            policy_version=policy.policy_version,
            expires_at=expires_at,
        )

        self.instrumentation.record_request_created(
            request_type=req_type.value,
            risk_level=risk.risk_level.value,
            status=status.value,
        )

        # If auto-approved, register immutable decision record immediately
        if status == ApprovalStatus.APPROVED:
            await self.decision_service.record_decision(
                organization_id=organization_id,
                request_id=request_id,
                decision=ApprovalStatus.APPROVED,
                reviewer_ids=["SYSTEM_AUTO_APPROVER"],
                policy_version=policy.policy_version,
                risk_score=risk.risk_score,
            )
            self.instrumentation.record_approval_granted(
                request_type=req_type.value,
                risk_level=risk.risk_level.value,
                decision="auto_approved",
            )
            logger.info(
                "Governance action automatically approved",
                extra={
                    "event": AUDIT_APPROVAL_APPROVED,
                    "approval_id": str(request_id),
                    "organization_id": str(organization_id),
                },
            )

        return self._to_domain_request(record)

    async def get_request(
        self, organization_id: uuid.UUID, request_id: uuid.UUID
    ) -> ApprovalRequest:
        """Fetch request within tenant boundary."""
        record = await self.repo.get_request(organization_id, request_id)
        if not record:
            raise ApprovalNotFoundError(
                f"Approval request {request_id} not found for organization {organization_id}"
            )
        return self._to_domain_request(record)

    async def list_requests(
        self,
        organization_id: uuid.UUID,
        status: ApprovalStatus | None = None,
        request_type: ApprovalType | None = None,
        risk_level: RiskLevel | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        """List requests for tenant."""
        records = await self.repo.list_requests(
            organization_id=organization_id,
            status=status.value if status else None,
            request_type=request_type.value if request_type else None,
            risk_level=risk_level.value if risk_level else None,
            limit=limit,
            offset=offset,
        )
        return [self._to_domain_request(r) for r in records]

    async def list_high_risk_requests(
        self,
        organization_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        """List high-risk and critical requests."""
        records = await self.repo.list_high_risk_requests(
            organization_id=organization_id,
            limit=limit,
            offset=offset,
        )
        return [self._to_domain_request(r) for r in records]

    async def cast_vote(
        self,
        organization_id: uuid.UUID,
        request_id: uuid.UUID,
        reviewer_id: uuid.UUID,
        decision: VoteDecision,
        comment: str | None = None,
    ) -> tuple[ApprovalRequest, ApprovalQuorum]:
        """Submit a reviewer vote, enforce separation of duties, and check quorum."""
        record = await self.repo.get_request(organization_id, request_id)
        if not record:
            raise ApprovalNotFoundError(
                f"Approval request {request_id} not found for organization {organization_id}"
            )

        current_status = ApprovalStatus(record.status)
        now = datetime.now(UTC)

        # 1. State machine check
        if current_status in (
            ApprovalStatus.APPROVED,
            ApprovalStatus.REJECTED,
            ApprovalStatus.CANCELLED,
            ApprovalStatus.REVOKED,
        ):
            raise InvalidStateTransitionError(
                f"Cannot vote on approval request in terminal state: {current_status.value}"
            )
        if current_status == ApprovalStatus.EXPIRED or (
            record.expires_at and record.expires_at <= now
        ):
            record.status = ApprovalStatus.EXPIRED.value
            await self.repo.session.flush()
            raise ApprovalExpiredError(f"Approval request {request_id} has expired")

        # 2. Separation of Duties: Requester cannot be sole approver
        policy = await self.policy_service.get_policy_by_version(
            organization_id, record.policy_version
        )
        req_risk = RiskLevel(record.risk_level)
        req_type = ApprovalType(record.request_type)
        requirement = self.policy_service.evaluate_requirement(
            policy=policy,
            risk=RiskAssessment(risk_level=req_risk, risk_score=record.risk_score),
            request_type=req_type,
        )

        is_self_review = reviewer_id == record.requester_id
        is_agent_requester = bool(record.context and record.context.get("is_agent", False))

        if is_self_review and (
            requirement.disallow_self_approval or req_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        ):
            raise SelfApprovalError(
                "Separation of duties violation: Requester cannot approve their own high-risk request"
            )
        if is_agent_requester and is_self_review:
            raise SelfApprovalError("Autonomous Agent cannot approve its own request")

        # 3. Transition to IN_REVIEW if PENDING
        if current_status == ApprovalStatus.PENDING:
            record.status = ApprovalStatus.IN_REVIEW.value
            logger.info(
                "Approval review started",
                extra={
                    "event": AUDIT_APPROVAL_STARTED,
                    "approval_id": str(request_id),
                    "reviewer_id": str(reviewer_id),
                },
            )

        # 4. Record vote
        await self.repo.create_vote(
            organization_id=organization_id,
            approval_request_id=request_id,
            reviewer_id=reviewer_id,
            decision=decision.value,
            comment=comment,
        )

        # 5. Evaluate Quorum
        all_votes = await self.repo.get_votes_for_request(organization_id, request_id)
        approved_count = sum(1 for v in all_votes if v.decision == VoteDecision.APPROVE.value)
        rejected_count = sum(1 for v in all_votes if v.decision == VoteDecision.REJECT.value)
        changes_count = sum(
            1 for v in all_votes if v.decision == VoteDecision.REQUEST_CHANGES.value
        )

        quorum = ApprovalQuorum(
            required=requirement.minimum_approvers,
            approved=approved_count,
            rejected=rejected_count,
            changes_requested=changes_count,
        )

        # 6. Apply Final Outcome if Quorum reached or Rejected
        if decision == VoteDecision.REJECT:
            record.status = ApprovalStatus.REJECTED.value
            reviewer_ids = [str(v.reviewer_id) for v in all_votes]
            await self.decision_service.record_decision(
                organization_id=organization_id,
                request_id=request_id,
                decision=ApprovalStatus.REJECTED,
                reviewer_ids=reviewer_ids,
                policy_version=record.policy_version,
                risk_score=record.risk_score,
            )
            self.instrumentation.record_approval_rejected(
                request_type=record.request_type,
                risk_level=record.risk_level,
                decision="rejected",
            )
            logger.info(
                "Approval request rejected",
                extra={"event": AUDIT_APPROVAL_REJECTED, "approval_id": str(request_id)},
            )

        elif decision == VoteDecision.REQUEST_CHANGES:
            record.status = ApprovalStatus.CHANGES_REQUESTED.value
            logger.info(
                "Changes requested on approval",
                extra={"event": AUDIT_APPROVAL_CHANGES_REQUESTED, "approval_id": str(request_id)},
            )

        elif quorum.is_reached:
            record.status = ApprovalStatus.APPROVED.value
            reviewer_ids = [
                str(v.reviewer_id) for v in all_votes if v.decision == VoteDecision.APPROVE.value
            ]
            await self.decision_service.record_decision(
                organization_id=organization_id,
                request_id=request_id,
                decision=ApprovalStatus.APPROVED,
                reviewer_ids=reviewer_ids,
                policy_version=record.policy_version,
                risk_score=record.risk_score,
            )
            latency_sec = (now - record.created_at).total_seconds() if record.created_at else 0.0
            self.instrumentation.record_approval_granted(
                request_type=record.request_type,
                risk_level=record.risk_level,
                decision="approved",
                latency_seconds=latency_sec,
            )
            logger.info(
                "Approval request reached quorum and was approved",
                extra={"event": AUDIT_APPROVAL_APPROVED, "approval_id": str(request_id)},
            )

        record.updated_at = now
        await self.repo.session.flush()

        refreshed = await self.repo.get_request(organization_id, request_id)
        return self._to_domain_request(refreshed or record), quorum

    async def revoke_approval(
        self,
        organization_id: uuid.UUID,
        request_id: uuid.UUID,
        revoker_id: uuid.UUID,
        reason: str,
    ) -> ApprovalRequest:
        """Revoke a previously approved request before execution begins."""
        record = await self.repo.get_request(organization_id, request_id)
        if not record:
            raise ApprovalNotFoundError(f"Approval request {request_id} not found")

        current_status = ApprovalStatus(record.status)
        if current_status != ApprovalStatus.APPROVED:
            raise InvalidStateTransitionError(
                f"Only APPROVED requests can be revoked. Current status is {current_status.value}"
            )

        record.status = ApprovalStatus.REVOKED.value
        record.updated_at = datetime.now(UTC)
        await self.repo.session.flush()

        logger.info(
            "Approval revoked",
            extra={
                "event": AUDIT_APPROVAL_REVOKED,
                "approval_id": str(request_id),
                "revoker_id": str(revoker_id),
                "reason": reason,
            },
        )
        return self._to_domain_request(record)

    async def cancel_request(
        self,
        organization_id: uuid.UUID,
        request_id: uuid.UUID,
        canceller_id: uuid.UUID,
    ) -> ApprovalRequest:
        """Cancel a pending approval request."""
        record = await self.repo.get_request(organization_id, request_id)
        if not record:
            raise ApprovalNotFoundError(f"Approval request {request_id} not found")

        current_status = ApprovalStatus(record.status)
        if current_status not in (
            ApprovalStatus.PENDING,
            ApprovalStatus.IN_REVIEW,
            ApprovalStatus.CHANGES_REQUESTED,
        ):
            raise InvalidStateTransitionError(
                f"Cannot cancel request in status {current_status.value}"
            )

        record.status = ApprovalStatus.CANCELLED.value
        record.updated_at = datetime.now(UTC)
        await self.repo.session.flush()

        logger.info(
            "Approval cancelled",
            extra={
                "event": AUDIT_APPROVAL_CANCELLED,
                "approval_id": str(request_id),
                "canceller_id": str(canceller_id),
            },
        )
        return self._to_domain_request(record)

    def _to_domain_request(self, model: Any) -> ApprovalRequest:
        """Helper to convert ORM model to domain dataclass safely without triggering async lazy loads."""
        domain_votes = []
        if "votes" in getattr(model, "__dict__", {}):
            domain_votes = [
                ApprovalVote(
                    id=v.id,
                    approval_request_id=v.approval_request_id,
                    organization_id=v.organization_id,
                    reviewer_id=v.reviewer_id,
                    decision=VoteDecision(v.decision),
                    comment=v.comment,
                    created_at=v.created_at,
                )
                for v in model.votes
            ]

        domain_comments = []
        if "comments" in getattr(model, "__dict__", {}):
            domain_comments = [
                ApprovalComment(
                    id=c.id,
                    approval_request_id=c.approval_request_id,
                    organization_id=c.organization_id,
                    author_id=c.author_id,
                    comment=c.comment,
                    created_at=c.created_at,
                )
                for c in model.comments
            ]
        return ApprovalRequest(
            id=model.id,
            organization_id=model.organization_id,
            request_type=ApprovalType(model.request_type),
            requester_id=model.requester_id,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            risk_level=RiskLevel(model.risk_level),
            risk_score=model.risk_score,
            status=ApprovalStatus(model.status),
            reason=model.reason,
            context=model.context or {},
            action_hash=model.action_hash,
            resource_hash=model.resource_hash,
            policy_version=model.policy_version,
            expires_at=model.expires_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            votes=domain_votes,
            comments=domain_comments,
        )
