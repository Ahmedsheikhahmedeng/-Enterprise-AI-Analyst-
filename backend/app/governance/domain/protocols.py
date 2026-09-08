"""Protocols and interfaces for Enterprise Governance."""

from typing import Any, Protocol
from uuid import UUID

from app.governance.domain.enums import ApprovalStatus, ApprovalType
from app.governance.domain.models import (
    ApprovalRequest,
    ApprovalRequirement,
    GovernancePolicy,
    RiskAssessment,
)


class ApprovalNotificationProvider(Protocol):
    """Notification abstraction for human reviewers (default: IN_APP)."""

    async def notify_approval_requested(
        self,
        request: ApprovalRequest,
        candidate_reviewer_roles: list[str],
    ) -> None:
        """Dispatch notification to eligible reviewers upon new pending request."""
        ...

    async def notify_status_changed(
        self,
        request: ApprovalRequest,
        old_status: ApprovalStatus,
        new_status: ApprovalStatus,
    ) -> None:
        """Notify stakeholders when an approval transitions to a new state."""
        ...


class RiskAssessorProtocol(Protocol):
    """Protocol for calculating deterministic risk levels and weighted risk scores."""

    def assess_risk(
        self,
        request_type: ApprovalType,
        factors: dict[str, Any],
    ) -> RiskAssessment:
        """Compute deterministic risk assessment from input factors."""
        ...


class GovernancePolicyEngineProtocol(Protocol):
    """Protocol for evaluating organization policies against assessed risk."""

    def evaluate_requirement(
        self,
        policy: GovernancePolicy,
        risk: RiskAssessment,
        request_type: ApprovalType,
    ) -> ApprovalRequirement:
        """Determine whether human approval is mandated, along with quorum and role constraints."""
        ...


class PreExecutionGateProtocol(Protocol):
    """Protocol for cryptographic TOCTOU verification and pre-execution authorization."""

    async def verify_and_authorize(
        self,
        approval_id: UUID,
        organization_id: UUID,
        current_action_payload: Any,
        resource_id: str | None = None,
    ) -> bool:
        """Verify approval status, expiration, quorum, and action_hash before permitting execution."""
        ...
