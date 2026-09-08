from typing import Any


class ComplianceError(Exception):
    """Base exception for all compliance and governance errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class PolicyViolationError(ComplianceError):
    """Raised when an operation violates data handling, LLM routing, or export policies."""

    def __init__(
        self, message: str, classification: str | None = None, policy_action: str | None = None
    ) -> None:
        super().__init__(message, {"classification": classification, "action": policy_action})


class LegalHoldActiveError(ComplianceError):
    """Raised when an operation cannot proceed because a target resource is under active legal hold."""

    def __init__(self, message: str, resource_id: str | None = None) -> None:
        super().__init__(message, {"resource_id": resource_id})


class UnapprovedRiskAcceptanceError(ComplianceError):
    """Raised when risk acceptance for a critical finding lacks privileged approval."""

    def __init__(self, message: str, finding_id: str | None = None) -> None:
        super().__init__(message, {"finding_id": finding_id})


class AuditIntegrityError(ComplianceError):
    """Raised when audit log cryptographic hash chain validation detects tampering or truncation."""

    def __init__(
        self, message: str, record_id: str | None = None, expected_hash: str | None = None
    ) -> None:
        super().__init__(message, {"record_id": record_id, "expected_hash": expected_hash})


class PrivacyRequestError(ComplianceError):
    """Raised when a data privacy request encounters an illegal state transition or invalid actor."""

    def __init__(
        self, message: str, request_id: str | None = None, status: str | None = None
    ) -> None:
        super().__init__(message, {"request_id": request_id, "status": status})
