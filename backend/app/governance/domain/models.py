"""Domain models for Enterprise Governance & Human-in-the-Loop Workflow."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.governance.domain.enums import (
    ApprovalStatus,
    ApprovalType,
    RiskLevel,
    VoteDecision,
)


@dataclass(frozen=True)
class RiskAssessment:
    """Calculated risk evaluation for a sensitive operation."""

    risk_level: RiskLevel
    risk_score: float
    reasons: list[str] = field(default_factory=list)
    factors: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ApprovalRequirement:
    """Policy-mandated review criteria for an operation."""

    required: bool
    minimum_approvers: int = 1
    required_roles: list[str] = field(default_factory=lambda: ["Admin"])
    required_permission: str = "governance.approve"
    timeout_minutes: int = 1440
    disallow_self_approval: bool = True


@dataclass(frozen=True)
class ApprovalQuorum:
    """Vote tally and quorum status."""

    required: int
    approved: int
    rejected: int
    changes_requested: int = 0

    @property
    def is_reached(self) -> bool:
        """Return true if approved votes meet or exceed requirement."""
        return self.approved >= self.required

    @property
    def is_rejected(self) -> bool:
        """Return true if rejection votes prevent reaching quorum."""
        return self.rejected > 0


@dataclass
class ApprovalVote:
    """A formal review vote on an approval request."""

    id: UUID
    approval_request_id: UUID
    organization_id: UUID
    reviewer_id: UUID
    decision: VoteDecision
    comment: str | None = None
    created_at: datetime | None = None


@dataclass
class ApprovalDecision:
    """Immutable audit record of a final approval or rejection resolution."""

    id: UUID
    request_id: UUID
    organization_id: UUID
    decision: ApprovalStatus
    reviewer_ids: list[str]
    policy_version: int
    risk_score: float
    decision_hash: str
    created_at: datetime | None = None


@dataclass
class ApprovalComment:
    """Discussion or review feedback note on an approval request."""

    id: UUID
    approval_request_id: UUID
    organization_id: UUID
    author_id: UUID
    comment: str
    created_at: datetime | None = None


@dataclass
class ApprovalRequest:
    """Governed operation request awaiting automated or human approval."""

    id: UUID
    organization_id: UUID
    request_type: ApprovalType
    requester_id: UUID
    resource_type: str
    resource_id: str | None
    risk_level: RiskLevel
    risk_score: float
    status: ApprovalStatus
    reason: str | None
    context: dict[str, Any]
    action_hash: str | None
    resource_hash: str | None
    policy_version: int
    expires_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
    votes: list[ApprovalVote] = field(default_factory=list)
    comments: list[ApprovalComment] = field(default_factory=list)


@dataclass
class GovernancePolicy:
    """Tenant-specific or default versioned governance policy."""

    id: UUID
    organization_id: UUID
    policy_version: int
    rules: dict[str, Any]
    status: str
    created_by: UUID | None = None
    approved_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
