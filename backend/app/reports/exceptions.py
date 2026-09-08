"""Domain exceptions for report generation, validation, versioning, and export."""

from typing import Any

from starlette import status

from app.core.exceptions import AppException


class ReportError(AppException):
    """Base exception for all report errors."""

    def __init__(
        self,
        message: str = "An error occurred within the report subsystem",
        code: str = "REPORT_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class ReportNotFoundError(ReportError):
    """Raised when a report or report version is not found."""

    def __init__(
        self,
        message: str = "Report not found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REPORT_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ReportAuthorizationError(ReportError):
    """Raised when a cross-tenant report access is attempted or permission is denied."""

    def __init__(
        self,
        message: str = "Access to the requested report is unauthorized",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REPORT_FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ReportValidationError(ReportError):
    """Raised when report structure, citations, or metrics fail validation."""

    def __init__(
        self,
        message: str = "Report failed validation checks",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REPORT_VALIDATION_ERROR",
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


class ReportVersionConflictError(ReportError):
    """Raised when an illegal mutation to a published immutable report is attempted."""

    def __init__(
        self,
        message: str = "Published report versions are immutable and cannot be overwritten",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REPORT_VERSION_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ReportExportError(ReportError):
    """Raised when formatting, rendering, or exporting a report fails."""

    def __init__(
        self,
        message: str = "Failed to export report",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REPORT_EXPORT_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class ReportGenerationError(ReportError):
    """Raised when generating a report from analysis run fails."""

    def __init__(
        self,
        message: str = "Failed to generate report from analysis",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="REPORT_GENERATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class UnsupportedExportFormatError(ReportError):
    """Raised when an unrecognized or unsupported export format is requested."""

    def __init__(
        self,
        format_name: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"Unsupported export format: {format_name}",
            code="UNSUPPORTED_EXPORT_FORMAT",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )
