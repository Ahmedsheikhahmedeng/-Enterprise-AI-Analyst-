"""Domain exception hierarchy for Enterprise Governance & Human-in-the-Loop Workflow."""


class GovernanceError(Exception):
    """Base class for all governance and approval workflow exceptions."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ApprovalNotFoundError(GovernanceError):
    """Raised when an approval request cannot be located within tenant scope."""


class InvalidStateTransitionError(GovernanceError):
    """Raised when attempting an illegal approval state transition."""


class SelfApprovalError(GovernanceError):
    """Raised when an entity or user attempts to approve their own request under strict separation of duties."""


class QuorumNotReachedError(GovernanceError):
    """Raised when an action is executed before meeting the required multi-approver quorum."""


class ApprovalExpiredError(GovernanceError):
    """Raised when interacting with or attempting to execute an expired approval request."""


class ApprovalRevokedError(GovernanceError):
    """Raised when an action is attempted on an approval that has been revoked."""


class TOCTOUMismatchError(GovernanceError):
    """Raised when execution parameters do not match the cryptographic action or resource hash at approval time."""


class PolicyNotFoundError(GovernanceError):
    """Raised when an organization governance policy is missing."""


class PolicyViolationError(GovernanceError):
    """Raised when an operation violates organization governance rules."""


class UnauthorizedReviewerError(GovernanceError):
    """Raised when a user lacks required permissions, is cross-tenant, or fails reviewer criteria."""


class PreExecutionBlockedError(GovernanceError):
    """Raised by pre-execution gates when an operation is blocked due to governance constraints."""
