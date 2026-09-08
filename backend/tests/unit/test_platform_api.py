"""Unit tests for Enterprise Platform APIs, Canonical Envelopes, Progress, and Sanitization — TASK 34."""

import uuid
from datetime import UTC, datetime

from app.api.v1.platform.progress import ProgressTracker
from app.api.v1.platform.sanitization import sanitize_event_payload
from app.api.v1.platform.schemas.common import (
    ApiResponse,
    PaginatedData,
)
from app.api.v1.platform.schemas.errors import (
    ApprovalRequiredException,
    InsufficientEvidenceException,
    PlatformErrorCode,
    RateLimitedException,
    TenantAccessDeniedException,
)
from app.api.v1.platform.schemas.execution import (
    ExecutionSummary,
)
from app.api.v1.platform.schemas.streaming import SSEEventType, StreamEvent
from app.security.replay import IdempotencyManager


def test_canonical_api_response_success() -> None:
    """Verify success envelope structure and serialization."""
    data = {"status": "ok", "value": 42}
    resp = ApiResponse.ok(data=data, request_id="req-123", trace_id="tr-456")

    assert resp.success is True
    assert resp.data == data
    assert resp.error is None
    assert resp.meta.request_id == "req-123"
    assert resp.meta.trace_id == "tr-456"

    serialized = resp.model_dump()
    assert serialized["success"] is True
    assert serialized["data"]["value"] == 42
    assert serialized["error"] is None
    assert serialized["meta"]["request_id"] == "req-123"


def test_canonical_api_response_failure() -> None:
    """Verify error envelope structure without leaking traces or internals."""
    resp = ApiResponse.fail(
        code=PlatformErrorCode.INSUFFICIENT_EVIDENCE,
        message="Not enough evidence found.",
        request_id="req-999",
        trace_id="tr-999",
        retryable=False,
        details={"score": 0.2},
    )

    assert resp.success is False
    assert resp.data is None
    assert resp.error is not None
    assert resp.error.code == "INSUFFICIENT_EVIDENCE"
    assert resp.error.message == "Not enough evidence found."
    assert resp.error.retryable is False
    assert resp.error.details == {"score": 0.2}


def test_platform_exceptions() -> None:
    """Verify platform domain exceptions produce correct codes and status codes."""
    exc1 = InsufficientEvidenceException(details={"missing": True})
    assert exc1.code == PlatformErrorCode.INSUFFICIENT_EVIDENCE
    assert exc1.status_code == 422
    assert exc1.retryable is False

    exc2 = RateLimitedException(retry_after=45)
    assert exc2.code == PlatformErrorCode.RATE_LIMITED
    assert exc2.status_code == 429
    assert exc2.retryable is True
    assert exc2.details["retry_after"] == 45

    exc3 = ApprovalRequiredException()
    assert exc3.code == PlatformErrorCode.APPROVAL_REQUIRED
    assert exc3.status_code == 403

    exc4 = TenantAccessDeniedException()
    assert exc4.code == PlatformErrorCode.TENANT_ACCESS_DENIED
    assert exc4.status_code == 403


def test_stage_progress_weighted_calculator() -> None:
    """Verify 0-100% stage weighting adhering to enterprise specifications."""
    tracker = ProgressTracker()
    assert tracker.get_progress() == 0

    # Start UNDERSTANDING (10% weight -> 5% when in progress)
    p1 = tracker.start_stage("UNDERSTANDING")
    assert p1.status == "RUNNING"
    assert p1.progress == 5

    # Complete UNDERSTANDING (10%)
    p2 = tracker.complete_stage("UNDERSTANDING")
    assert p2.status == "COMPLETED"
    assert p2.progress == 10

    # Start and complete SEMANTIC (10%) -> 20%
    tracker.start_stage("SEMANTIC")
    p3 = tracker.complete_stage("SEMANTIC")
    assert p3.progress == 20

    # Complete GRAPH (10%) -> 30%
    tracker.start_stage("GRAPH")
    p4 = tracker.complete_stage("GRAPH")
    assert p4.progress == 30

    # Complete PLANNING (10%) -> 40%
    tracker.start_stage("PLANNING")
    p5 = tracker.complete_stage("PLANNING")
    assert p5.progress == 40

    # Complete EXECUTION (30%) -> 70%
    tracker.start_stage("EXECUTION")
    p6 = tracker.complete_stage("EXECUTION")
    assert p6.progress == 70

    # Complete EVIDENCE (10%) -> 80%
    tracker.start_stage("EVIDENCE")
    p7 = tracker.complete_stage("EVIDENCE")
    assert p7.progress == 80

    # Complete VERIFICATION (10%) -> 90%
    tracker.start_stage("VERIFICATION")
    p8 = tracker.complete_stage("VERIFICATION")
    assert p8.progress == 90

    # Complete RESPONSE (10%) -> 100%
    tracker.start_stage("RESPONSE")
    p9 = tracker.complete_stage("RESPONSE")
    assert p9.progress == 100

    summary = tracker.export_summary()
    assert len(summary) == 8
    assert all(s["status"] == "COMPLETED" for s in summary)


def test_event_payload_sanitization() -> None:
    """Verify recursive scrubbing of secrets, passwords, system prompts, and stack traces."""
    dirty_payload = {
        "title": "Quarterly Report",
        "api_key": "sk-secret-token-1234567890",
        "password": "SuperSecretPassword123!",
        "system_prompt": "You are a private LLM instructed to...",
        "raw_prompt": "Tell me secrets...",
        "stack_trace": "File app.py line 20 in run... ZeroDivisionError",
        "nested": {
            "token": "bearer-xyz",
            "safe_metric": 42.5,
            "secret_credential": "hidden",
            "instructions": "Normal customer instruction text",
        },
        "items": [
            {"id": "S1", "api_token": "leak"},
            "Normal item text with Bearer eyJhbGciOi token inside",
        ],
    }

    clean = sanitize_event_payload(dirty_payload)

    # Forbidden keys must be scrubbed
    assert "api_key" not in clean
    assert "password" not in clean
    assert "system_prompt" not in clean
    assert "raw_prompt" not in clean
    assert "stack_trace" not in clean
    assert clean["title"] == "Quarterly Report"

    # Nested scrubbing
    assert "token" not in clean["nested"]
    assert "secret_credential" not in clean["nested"]
    assert clean["nested"]["safe_metric"] == 42.5

    # List scrubbing
    assert "api_token" not in clean["items"][0]
    assert clean["items"][0]["id"] == "S1"


def test_idempotency_fingerprint_generation() -> None:
    """Verify SHA-256 fingerprint generation for POST /ask."""
    fp1 = IdempotencyManager.compute_fingerprint(
        method="POST", path="/api/v1/ask", body='{"question": "test"}'
    )
    fp2 = IdempotencyManager.compute_fingerprint(
        method="POST", path="/api/v1/ask", body='{"question": "test"}'
    )
    fp3 = IdempotencyManager.compute_fingerprint(
        method="POST", path="/api/v1/ask", body='{"question": "different"}'
    )

    assert fp1 == fp2
    assert fp1 != fp3


def test_stream_event_sse_formatting() -> None:
    """Verify SSE line formatting conforming to text/event-stream spec."""
    evt = StreamEvent(
        event=SSEEventType.EXECUTION_STARTED,
        execution_id="12345678-1234-1234-1234-123456789012",
        timestamp="2026-09-07T14:00:00Z",
        sequence=1,
        data={"mode": "AUTO"},
    )

    wire = evt.to_sse_format()
    assert wire.startswith("event: execution.started\n")
    assert "id: 1\n" in wire
    assert 'data: {"event": "execution.started"' in wire
    assert wire.endswith("\n\n")


def test_paginated_data_contract() -> None:
    """Verify paginated collection wrapper and cursor generation."""
    items = [
        ExecutionSummary(
            id=uuid.uuid4(),
            query="SELECT 1",
            status="COMPLETED",
            mode="AUTO",
            decision="ANSWER",
            confidence_score=0.95,
            evidence_coverage=0.90,
            created_at=datetime.now(UTC),
        )
    ]
    p = PaginatedData[ExecutionSummary](
        items=items,
        total=1,
        page=1,
        page_size=20,
        cursor=None,
        has_more=False,
    )
    assert len(p.items) == 1
    assert p.total == 1
    assert p.has_more is False
