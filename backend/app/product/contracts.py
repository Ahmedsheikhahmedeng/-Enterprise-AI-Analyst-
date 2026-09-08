"""Canonical API envelopes, error formats, SSE events, and contract verification."""

from typing import Any

from pydantic import BaseModel, Field


class CanonicalErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CanonicalErrorResponse(BaseModel):
    error: CanonicalErrorDetail


class CanonicalResponseMeta(BaseModel):
    request_id: str | None = None
    timestamp: str | None = None
    tenant_id: str | None = None
    duration_ms: float | None = None


class CanonicalSuccessResponse[T](BaseModel):
    data: T
    meta: CanonicalResponseMeta | None = None


class CanonicalSSEEvent(BaseModel):
    event: str
    data: dict[str, Any]
    event_id: str | None = None
    retry: int | None = None


class ContractVerificationResult(BaseModel):
    contract_name: str
    is_valid: bool
    status_code: int | None = None
    violations: list[str] = Field(default_factory=list)


class ProductContractValidator:
    """Validates that API payloads, error structures, and event streams strictly adhere to enterprise contracts."""

    CANONICAL_ERROR_CODES: set[str] = {
        "BAD_REQUEST",
        "UNAUTHORIZED",
        "FORBIDDEN",
        "NOT_FOUND",
        "CONFLICT",
        "VALIDATION_ERROR",
        "RATE_LIMITED",
        "INTERNAL_SERVER_ERROR",
        "SERVICE_UNAVAILABLE",
        "COST_POLICY_VIOLATION",
        "BUDGET_EXCEEDED",
        "QUOTA_EXCEEDED",
        "DATA_CLASSIFICATION_VIOLATION",
    }

    @classmethod
    def validate_error_contract(
        cls, status_code: int, payload: dict[str, Any]
    ) -> ContractVerificationResult:
        violations: list[str] = []
        if "error" not in payload:
            violations.append("Payload missing top-level 'error' key.")
            return ContractVerificationResult(
                contract_name="ErrorEnvelopeContract",
                is_valid=False,
                status_code=status_code,
                violations=violations,
            )

        err = payload["error"]
        if not isinstance(err, dict):
            violations.append("'error' must be a JSON dictionary.")
            return ContractVerificationResult(
                contract_name="ErrorEnvelopeContract",
                is_valid=False,
                status_code=status_code,
                violations=violations,
            )

        if not err.get("code"):
            violations.append("'error.code' is required and non-empty.")
        if not err.get("message"):
            violations.append("'error.message' is required and non-empty.")

        # Ensure code matches recognized format
        code = str(err.get("code", ""))
        if (
            code not in cls.CANONICAL_ERROR_CODES
            and not code.startswith("HTTP_")
            and not (code.isupper() and all(c.isalnum() or c == "_" for c in code))
        ):
            violations.append(f"Error code '{code}' violates UPPER_SNAKE_CASE format.")

        return ContractVerificationResult(
            contract_name="ErrorEnvelopeContract",
            is_valid=len(violations) == 0,
            status_code=status_code,
            violations=violations,
        )

    @classmethod
    def validate_sse_stream_contract(
        cls, events: list[dict[str, Any]]
    ) -> ContractVerificationResult:
        violations: list[str] = []
        if not events:
            violations.append("SSE stream returned zero events.")

        saw_terminal = False
        for idx, ev in enumerate(events):
            if "event" not in ev:
                violations.append(f"Event at index {idx} missing 'event' type.")
            if "data" not in ev or not isinstance(ev["data"], dict):
                violations.append(f"Event at index {idx} missing dict 'data'.")

            event_type = ev.get("event")
            if event_type in {"done", "complete", "error"}:
                saw_terminal = True

        if events and not saw_terminal:
            violations.append("SSE stream terminated without a terminal event ('done' or 'error').")

        return ContractVerificationResult(
            contract_name="SSEStreamContract",
            is_valid=len(violations) == 0,
            violations=violations,
        )

    @classmethod
    def validate_correlation_contract(cls, headers: dict[str, str]) -> ContractVerificationResult:
        violations: list[str] = []
        lower_headers = {k.lower(): v for k, v in headers.items()}
        req_id = lower_headers.get("x-request-id")
        if not req_id or not req_id.strip():
            violations.append("Missing required 'X-Request-ID' header.")

        return ContractVerificationResult(
            contract_name="CorrelationHeaderContract",
            is_valid=len(violations) == 0,
            violations=violations,
        )
