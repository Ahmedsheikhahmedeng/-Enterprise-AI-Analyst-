"""Domain exceptions for Enterprise AI Evaluation & Quality Framework."""

from typing import Any

from starlette import status

from app.core.exceptions import AppException


class EvaluationError(AppException):
    """Base exception for all evaluation errors."""

    def __init__(
        self,
        message: str = "An error occurred within the evaluation subsystem",
        code: str = "EVALUATION_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class EvaluationDatasetNotFoundError(EvaluationError):
    """Raised when an evaluation dataset or version is not found."""

    def __init__(
        self,
        message: str = "Evaluation dataset not found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EVALUATION_DATASET_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class EvaluationCaseNotFoundError(EvaluationError):
    """Raised when an evaluation case is not found."""

    def __init__(
        self,
        message: str = "Evaluation case not found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EVALUATION_CASE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class EvaluationRunNotFoundError(EvaluationError):
    """Raised when an evaluation benchmark run is not found."""

    def __init__(
        self,
        message: str = "Evaluation run not found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EVALUATION_RUN_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class EvaluationAuthorizationError(EvaluationError):
    """Raised when cross-tenant access to evaluation datasets or runs is attempted."""

    def __init__(
        self,
        message: str = "Access to the requested evaluation resource is unauthorized",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EVALUATION_UNAUTHORIZED",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class EvaluationValidationError(EvaluationError):
    """Raised when evaluation case or dataset input fails validation."""

    def __init__(
        self,
        message: str = "Evaluation validation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EVALUATION_VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class EvaluationExecutionError(EvaluationError):
    """Raised when an unexpected error occurs during benchmark execution."""

    def __init__(
        self,
        message: str = "Evaluation execution failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EVALUATION_EXECUTION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class RegressionThresholdExceededError(EvaluationError):
    """Raised when regression comparison fails configured quality thresholds."""

    def __init__(
        self,
        message: str = "Benchmark run exceeded allowed regression threshold",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REGRESSION_THRESHOLD_EXCEEDED",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )
