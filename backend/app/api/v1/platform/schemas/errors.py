"""Standardized Error Codes and Error Contract Definitions — TASK 34."""

from enum import StrEnum
from typing import Any


class PlatformErrorCode(StrEnum):
    """Canonical error codes required by the enterprise frontend specification."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    TENANT_ACCESS_DENIED = "TENANT_ACCESS_DENIED"
    RATE_LIMITED = "RATE_LIMITED"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class PlatformException(Exception):
    """Base exception for platform domain errors returning canonical error envelope."""

    def __init__(
        self,
        code: PlatformErrorCode | str,
        message: str,
        status_code: int = 400,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.status_code = status_code
        self.retryable = retryable
        self.details = details or {}


class InsufficientEvidenceException(PlatformException):
    def __init__(
        self,
        message: str = "Insufficient evidence to answer query with high confidence.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=PlatformErrorCode.INSUFFICIENT_EVIDENCE,
            message=message,
            status_code=422,
            retryable=False,
            details=details,
        )


class ConflictingEvidenceException(PlatformException):
    def __init__(
        self,
        message: str = "Conflicting evidence detected across information sources.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=PlatformErrorCode.CONFLICTING_EVIDENCE,
            message=message,
            status_code=422,
            retryable=False,
            details=details,
        )


class ApprovalRequiredException(PlatformException):
    def __init__(
        self,
        message: str = "Operation requires human review and authorization before proceeding.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=PlatformErrorCode.APPROVAL_REQUIRED,
            message=message,
            status_code=403,
            retryable=False,
            details=details,
        )


class RateLimitedException(PlatformException):
    def __init__(
        self,
        message: str = "Rate limit exceeded. Please retry after the specified window.",
        retry_after: int = 60,
        details: dict[str, Any] | None = None,
    ) -> None:
        merged_details = details or {}
        merged_details["retry_after"] = retry_after
        super().__init__(
            code=PlatformErrorCode.RATE_LIMITED,
            message=message,
            status_code=429,
            retryable=True,
            details=merged_details,
        )


class TenantAccessDeniedException(PlatformException):
    def __init__(
        self,
        message: str = "Access to resources belonging to another tenant is strictly denied.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=PlatformErrorCode.TENANT_ACCESS_DENIED,
            message=message,
            status_code=403,
            retryable=False,
            details=details,
        )


class ProcessingFailedException(PlatformException):
    def __init__(
        self,
        message: str = "Execution processing failed during pipeline orchestration.",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            code=PlatformErrorCode.PROCESSING_FAILED,
            message=message,
            status_code=500,
            retryable=retryable,
            details=details,
        )
