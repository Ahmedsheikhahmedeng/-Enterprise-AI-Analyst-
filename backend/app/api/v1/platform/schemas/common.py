"""Canonical API Response Envelopes, Pagination & Metadata Schemas — TASK 34."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResponseMeta(BaseModel):
    """Metadata context included on every canonical API response."""

    model_config = ConfigDict(extra="ignore")

    request_id: str = Field(..., description="Unique correlation identifier for the HTTP request")
    trace_id: str = Field(..., description="Distributed tracing identifier (W3C or hex)")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp of response generation",
    )


class ApiError(BaseModel):
    """Standardized error contract eliminating internal exceptions, SQL, secrets, or traces."""

    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., description="Machine-readable standardized error code")
    message: str = Field(..., description="Human-readable safe error message for the frontend")
    request_id: str | None = Field(None, description="Request ID associated with the error")
    retryable: bool = Field(False, description="Whether the client may retry the operation")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured safe context (e.g. validation errors, missing fields)",
    )


class ApiResponse[T](BaseModel):
    """Canonical production API response envelope for all platform endpoints."""

    model_config = ConfigDict(extra="ignore")

    success: bool = Field(..., description="Whether the request succeeded")
    data: T | None = Field(None, description="Typed response payload on success, null on error")
    error: ApiError | None = Field(
        None, description="Structured error details on failure, null on success"
    )
    meta: ResponseMeta = Field(..., description="Correlation and execution metadata")

    @classmethod
    def ok(
        cls,
        data: T,
        request_id: str = "unknown",
        trace_id: str = "unknown",
    ) -> "ApiResponse[T]":
        """Factory for successful response envelope."""
        return cls(
            success=True,
            data=data,
            error=None,
            meta=ResponseMeta(request_id=request_id, trace_id=trace_id),
        )

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        request_id: str = "unknown",
        trace_id: str = "unknown",
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> "ApiResponse[Any]":
        """Factory for failed response envelope."""
        return cls(
            success=False,
            data=None,
            error=ApiError(
                code=code,
                message=message,
                request_id=request_id,
                retryable=retryable,
                details=details or {},
            ),
            meta=ResponseMeta(request_id=request_id, trace_id=trace_id),
        )


class PaginationParams(BaseModel):
    """Standard offset-based pagination query parameters."""

    page: int = Field(1, ge=1, description="1-indexed page number")
    page_size: int = Field(20, ge=1, le=100, description="Number of records per page")


class CursorPaginationParams(BaseModel):
    """Cursor-based pagination query parameters for high-volume collections."""

    cursor: str | None = Field(None, description="Opaque cursor token for the next page")
    limit: int = Field(20, ge=1, le=100, description="Maximum number of items to return")


class PaginatedData[T](BaseModel):
    """Generic payload wrapper for paginated collections."""

    model_config = ConfigDict(extra="ignore")

    items: list[T] = Field(default_factory=list)
    total: int = Field(..., ge=0)
    page: int | None = Field(default=None, ge=1)
    page_size: int | None = Field(default=None, ge=1)
    cursor: str | None = Field(default=None)
    has_more: bool = Field(default=False)
