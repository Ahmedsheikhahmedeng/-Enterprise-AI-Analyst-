from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Structured error payload compliant with enterprise API contract."""

    model_config = ConfigDict(extra="allow")

    code: str = Field(
        ...,
        description="Machine-readable unique error code",
        examples=["VALIDATION_ERROR", "NOT_FOUND", "INTERNAL_SERVER_ERROR"],
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the error",
        examples=["Resource not found"],
    )
    request_id: str = Field(
        ...,
        description="Correlation request identifier for troubleshooting",
        examples=["req_01HPX7K94N2V"],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional supplementary error metadata or field errors",
    )


class ErrorResponse(BaseModel):
    """Top-level standard error envelope for all error responses."""

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail
