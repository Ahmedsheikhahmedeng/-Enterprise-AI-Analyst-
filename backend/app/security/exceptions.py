"""Domain exception hierarchy for the security hardening layer."""

from typing import Any

from app.core.exceptions import AppException


class SecurityException(AppException):
    """Base exception for all security violations, ensuring consistent non-leaking responses."""

    def __init__(
        self,
        message: str = "A security policy constraint was violated.",
        code: str = "SECURITY_VIOLATION",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
        )


SecurityError = SecurityException


class ExportSecurityError(SecurityException):
    """Raised when an export operation violates security constraints or contains path traversal."""

    def __init__(
        self,
        message: str = "Export rejected by security policy.",
        code: str = "EXPORT_SECURITY_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=400,
            details=details,
        )


class SecurityPolicyViolationError(SecurityException):
    """Raised when an action violates global security policy constraints."""

    def __init__(
        self, message: str = "Security policy violation.", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="SECURITY_POLICY_VIOLATION",
            status_code=403,
            details=details,
        )


class PromptInjectionDetectedError(SecurityException):
    """Raised when high-risk adversarial prompt injection patterns are identified."""

    def __init__(
        self,
        message: str = "Unsafe input detected: request blocked by AI prompt security policy.",
        category: str = "adversarial_instruction",
        risk_score: float = 1.0,
    ) -> None:
        super().__init__(
            message=message,
            code="PROMPT_INJECTION_DETECTED",
            status_code=400,
            details={"category": category, "risk_score": risk_score},
        )


class SSRFBlockedError(SecurityException):
    """Raised when an outbound URL fetch targets a private, loopback, or metadata network."""

    def __init__(
        self,
        message: str = "Outbound network request blocked by SSRF defense policy.",
        target_host: str = "unknown",
        reason: str = "private_network_access",
    ) -> None:
        super().__init__(
            message=message,
            code="SSRF_REQUEST_BLOCKED",
            status_code=400,
            details={"target_host": target_host, "reason": reason},
        )


class FileSecurityError(SecurityException):
    """Raised when an uploaded file fails magic-byte, extension, or path sanitization checks."""

    def __init__(
        self,
        message: str = "File rejected by security validation policy.",
        reason: str = "invalid_file_signature",
    ) -> None:
        super().__init__(
            message=message,
            code="FILE_SECURITY_REJECTED",
            status_code=400,
            details={"reason": reason},
        )


class RateLimitExceededError(SecurityException):
    """Raised when client exceeds designated requests-per-minute quota."""

    def __init__(
        self,
        message: str = "Rate limit quota exceeded. Please slow down.",
        retry_after: int = 60,
        limit: int | None = None,
    ) -> None:
        self.retry_after = retry_after
        self.limit = limit
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={"retry_after": retry_after, "limit": limit},
        )


class ReplayViolationError(SecurityException):
    """Raised when a request conflicts with an active or executed idempotency key."""

    def __init__(
        self,
        message: str = "Idempotency key conflict: identical key reused with different request payload.",
        key: str = "",
    ) -> None:
        super().__init__(
            message=message,
            code="IDEMPOTENCY_KEY_CONFLICT",
            status_code=409,
            details={"idempotency_key": key},
        )


class TenantIsolationViolationError(SecurityException):
    """Raised when a caller attempts cross-tenant resource access."""

    def __init__(
        self,
        message: str = "Access denied: resource belongs to a different tenant organization.",
        resource_type: str = "unknown",
    ) -> None:
        super().__init__(
            message=message,
            code="TENANT_ISOLATION_VIOLATION",
            status_code=403,
            details={"resource_type": resource_type},
        )


class IDORViolationError(SecurityException):
    """Raised when an unauthorized resource identifier is queried directly."""

    def __init__(
        self,
        message: str = "Resource not found or access is unauthorized.",
        resource_id: str = "",
    ) -> None:
        super().__init__(
            message=message,
            code="IDOR_ACCESS_DENIED",
            status_code=403,
            details={"resource_id": resource_id},
        )
