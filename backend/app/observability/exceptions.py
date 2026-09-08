"""Domain exceptions for Enterprise Observability & Monitoring."""

from typing import Any

from starlette import status

from app.core.exceptions import AppException


class ObservabilityError(AppException):
    """Base exception for all observability and telemetry errors."""

    def __init__(
        self,
        message: str = "An error occurred within the observability subsystem",
        code: str = "OBSERVABILITY_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class ObservabilityAuthorizationError(ObservabilityError):
    """Raised when cross-tenant access to telemetry or unauthorized metrics access is attempted."""

    def __init__(
        self,
        message: str = "Unauthorized access to observability telemetry",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="OBSERVABILITY_UNAUTHORIZED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class InvalidTraceHeaderError(ObservabilityError):
    """Raised when an incoming trace header (e.g. W3C traceparent) is malformed."""

    def __init__(
        self,
        message: str = "Malformed or invalid distributed trace context header",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_TRACE_HEADER",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class MetricRegistrationError(ObservabilityError):
    """Raised when a metric definition is registered incorrectly or has type mismatches."""

    def __init__(
        self,
        message: str = "Metric registration error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="METRIC_REGISTRATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class HighCardinalityViolationError(ObservabilityError):
    """Raised when an attempt is made to use unbounded identifiers as metric labels."""

    def __init__(
        self,
        label_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"High-cardinality label '{label_name}' is forbidden on metric series.",
            code="HIGH_CARDINALITY_VIOLATION",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details or {"label": label_name},
        )
