from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, request_id_ctx_var

logger = get_logger("exceptions")


class AppException(Exception):
    """Base application exception from which all domain and HTTP errors derive."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class ValidationAppException(AppException):
    """Raised when input validation fails in business rules."""

    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            details=details,
        )


class BadRequestAppException(AppException):
    """Raised when request payload or parameters are semantically invalid."""

    def __init__(
        self,
        message: str = "Bad request",
        code: str = "BAD_REQUEST",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class NotFoundAppException(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class UnauthorizedAppException(AppException):
    """Raised when authentication credentials are missing or invalid."""

    def __init__(
        self,
        message: str = "Authentication required",
        code: str = "UNAUTHORIZED",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenAppException(AppException):
    """Raised when authenticated user lacks permissions for an operation."""

    def __init__(
        self,
        message: str = "Access forbidden",
        code: str = "FORBIDDEN",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ConflictAppException(AppException):
    """Raised when an operation conflicts with current state (e.g. duplicate resource)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class PayloadTooLargeAppException(AppException):
    """Raised when uploaded file or request payload exceeds permitted size limit."""

    def __init__(
        self,
        message: str = "Payload exceeds maximum allowed size",
        code: str = "PAYLOAD_TOO_LARGE",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            details=details,
        )


class InternalAppException(AppException):
    """Raised when an internal error occurs within an operation."""

    def __init__(
        self,
        message: str = "An internal server error occurred",
        code: str = "INTERNAL_SERVER_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def _resolve_request_id(request: Request) -> str:
    """Resolve active request_id from state or async context."""
    req_id = getattr(request.state, "request_id", None)
    if req_id:
        return str(req_id)
    ctx_val = request_id_ctx_var.get()
    return str(ctx_val) if ctx_val else "unknown"


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle known domain application exceptions with standard response envelope."""
    request_id = _resolve_request_id(request)
    logger.warning(
        "Application exception handled",
        error_code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
                **({"details": exc.details} if exc.details else {}),
            }
        },
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle FastAPI and Pydantic request validation errors."""
    request_id = _resolve_request_id(request)
    formatted_errors = [
        {
            "loc": [str(loc_item) for loc_item in err.get("loc", [])],
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    logger.warning(
        "Request validation error",
        errors=formatted_errors,
    )
    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The provided request payload or parameters failed validation.",
                "request_id": request_id,
                "details": {"validation_errors": formatted_errors},
            }
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected exceptions: logs trace and returns safe 500.

    Does not leak internal stack traces to the client.
    """
    request_id = _resolve_request_id(request)
    logger.error(
        "Unhandled internal server error",
        exc_info=exc,
        exception_type=exc.__class__.__name__,
        exception_message=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": (
                    "An unexpected error occurred. Please contact support with the request_id."
                ),
                "request_id": request_id,
            }
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle standard HTTP exceptions (e.g. 404, 405) with consistent error contract."""
    request_id = _resolve_request_id(request)
    code_mapping = {
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        403: "FORBIDDEN",
        401: "UNAUTHORIZED",
    }
    code = code_mapping.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = str(exc.detail) if exc.detail else "An HTTP error occurred"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )
