"""Exception hierarchy for the Cross-Encoder Reranking domain."""

from typing import Any

from app.core.exceptions import AppException


class RerankingError(AppException):
    """Base exception for all errors originating within the reranking domain."""

    def __init__(
        self,
        message: str = "Reranking operation failed",
        code: str = "RERANKING_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class RerankerConfigurationError(RerankingError):
    """Raised when reranker provider or parameters are invalid or misconfigured."""

    def __init__(
        self,
        message: str = "Invalid reranker configuration",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RERANKER_CONFIGURATION_ERROR",
            status_code=500,
            details=details,
        )


class RerankerModelLoadError(RerankingError):
    """Raised when cross-encoder model loading or initialization fails."""

    def __init__(
        self,
        message: str = "Failed to load cross-encoder reranker model",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RERANKER_MODEL_LOAD_ERROR",
            status_code=500,
            details=details,
        )


class RerankerInputError(RerankingError):
    """Raised when query or candidate sequence violates validation constraints."""

    def __init__(
        self,
        message: str = "Invalid reranker input candidates or query",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RERANKER_INPUT_ERROR",
            status_code=400,
            details=details,
        )


class RerankerTimeoutError(RerankingError):
    """Raised when cross-encoder inference exceeds the configured deadline."""

    def __init__(
        self,
        message: str = "Cross-encoder reranking operation timed out",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RERANKER_TIMEOUT_ERROR",
            status_code=504,
            details=details,
        )


class RerankerInferenceError(RerankingError):
    """Raised when model forward pass or tensor computation fails."""

    def __init__(
        self,
        message: str = "Cross-encoder model inference failure",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RERANKER_INFERENCE_ERROR",
            status_code=500,
            details=details,
        )


class RerankerUnavailableError(RerankingError):
    """Raised when reranking is invoked while disabled or in an unhealthy state."""

    def __init__(
        self,
        message: str = "Cross-encoder reranking service is currently unavailable",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RERANKER_UNAVAILABLE_ERROR",
            status_code=503,
            details=details,
        )


class RerankerTenantError(RerankingError):
    """Raised when a candidate chunk belongs to an organization outside tenant scope."""

    def __init__(
        self,
        message: str = "Cross-tenant candidate detected in reranking pool",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="RERANKER_TENANT_ISOLATION_ERROR",
            status_code=403,
            details=details,
        )
