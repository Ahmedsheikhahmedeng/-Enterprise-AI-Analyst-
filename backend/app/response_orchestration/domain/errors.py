"""Domain errors and exceptions for Response Orchestration."""

from typing import Any


class OrchestrationError(Exception):
    """Base exception for all Response Orchestration errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class OrchestrationTimeoutError(OrchestrationError):
    """Raised when execution exceeds allocated time budget."""


class OrchestrationBudgetExceededError(OrchestrationError):
    """Raised when query exceeds token, cost, or tool budget caps."""


class OrchestrationSecurityError(OrchestrationError):
    """Raised when tenant boundary or input sanitization policies are violated."""


class TenantMismatchError(OrchestrationSecurityError):
    """Raised when cross-tenant evidence, citation, or resource access is detected."""


class ClarificationLoopError(OrchestrationError):
    """Raised when clarification round limit is exceeded."""


class InvalidCitationError(OrchestrationError):
    """Raised when hallucinated or unverified citations are encountered."""
