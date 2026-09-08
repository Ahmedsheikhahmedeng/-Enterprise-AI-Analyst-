"""Domain enums and state machine transition rules for Enterprise Governance."""

from enum import StrEnum


class ApprovalType(StrEnum):
    """Controlled catalog of operations subject to enterprise governance."""

    QUERY_EXECUTION = "QUERY_EXECUTION"
    DATA_ACCESS = "DATA_ACCESS"
    DATA_EXPORT = "DATA_EXPORT"
    REPORT_PUBLICATION = "REPORT_PUBLICATION"
    SEMANTIC_PUBLICATION = "SEMANTIC_PUBLICATION"
    GRAPH_PUBLICATION = "GRAPH_PUBLICATION"
    MODEL_CHANGE = "MODEL_CHANGE"
    POLICY_CHANGE = "POLICY_CHANGE"
    AGENT_HIGH_RISK_ACTION = "AGENT_HIGH_RISK_ACTION"


class ApprovalStatus(StrEnum):
    """Strict lifecycle states for an approval request."""

    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REVOKED = "REVOKED"


class RiskLevel(StrEnum):
    """Risk tiers for governed actions."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VoteDecision(StrEnum):
    """Reviewer vote outcomes."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class PolicyDecision(StrEnum):
    """Action outcome from governance policy evaluation."""

    AUTO_APPROVE = "AUTO_APPROVE"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"
    DENY = "DENY"


# Legal State Machine Transitions
VALID_TRANSITIONS: dict[ApprovalStatus, set[ApprovalStatus]] = {
    ApprovalStatus.PENDING: {
        ApprovalStatus.IN_REVIEW,
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.CANCELLED,
    },
    ApprovalStatus.IN_REVIEW: {
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.CHANGES_REQUESTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.CANCELLED,
    },
    ApprovalStatus.CHANGES_REQUESTED: {
        ApprovalStatus.IN_REVIEW,
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.CANCELLED,
    },
    ApprovalStatus.APPROVED: {
        ApprovalStatus.REVOKED,
    },
    ApprovalStatus.REJECTED: set(),
    ApprovalStatus.EXPIRED: set(),
    ApprovalStatus.CANCELLED: set(),
    ApprovalStatus.REVOKED: set(),
}
