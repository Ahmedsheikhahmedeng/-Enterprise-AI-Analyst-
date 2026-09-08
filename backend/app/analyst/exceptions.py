"""Domain exception hierarchy for the Unified AI Analyst Orchestrator."""

from typing import Any

from starlette import status

from app.core.exceptions import AppException


class AnalystError(AppException):
    """Base exception for all errors within the unified analyst subsystem."""

    def __init__(
        self,
        message: str = "Analyst orchestration error occurred",
        code: str = "ANALYST_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class AnalystRoutingError(AnalystError):
    """Raised when routing or planning fails to determine a viable execution path."""

    def __init__(
        self,
        message: str = "Failed to route query to an appropriate data source",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ANALYST_ROUTING_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class AnalystTimeoutError(AnalystError):
    """Raised when execution exceeds the global analyst request deadline."""

    def __init__(
        self,
        message: str = "Analyst execution timed out",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ANALYST_TIMEOUT",
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            details=details,
        )


class AnalystTenantMismatchError(AnalystError):
    """Raised when a query references resources outside the authenticated tenant boundary."""

    def __init__(
        self,
        message: str = "Cross-tenant access prohibited in analyst orchestration",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ANALYST_TENANT_MISMATCH",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class AnalystBudgetExceededError(AnalystError):
    """Raised when request complexity exceeds allocated operational budgets."""

    def __init__(
        self,
        message: str = "Analyst query exceeded branch or evidence budget",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ANALYST_BUDGET_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )
