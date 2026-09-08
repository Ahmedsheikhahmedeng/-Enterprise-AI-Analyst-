"""Server-Sent Events (SSE) Streaming Schemas and Event Contracts — TASK 34."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SSEEventType(StrEnum):
    """Supported real-time execution lifecycle events."""

    EXECUTION_STARTED = "execution.started"
    EXECUTION_STAGE = "execution.stage"
    EXECUTION_PROGRESS = "execution.progress"
    SEMANTIC_RESOLVED = "semantic.resolved"
    GRAPH_RESOLVED = "graph.resolved"
    RETRIEVAL_STARTED = "retrieval.started"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    SQL_STARTED = "sql.started"
    SQL_COMPLETED = "sql.completed"
    EVIDENCE_COLLECTED = "evidence.collected"
    VERIFICATION_STARTED = "verification.started"
    DECISION_CREATED = "decision.created"
    APPROVAL_REQUIRED = "approval.required"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"
    RESPONSE_GENERATING = "response.generating"
    RESPONSE_CHUNK = "response.chunk"
    RESPONSE_COMPLETED = "response.completed"
    EXECUTION_FAILED = "execution.failed"
    EXECUTION_CANCELLED = "execution.cancelled"
    HEARTBEAT = "heartbeat"


class StreamEvent(BaseModel):
    """Canonical event structure transmitted over Server-Sent Events."""

    model_config = ConfigDict(extra="ignore")

    event: str = Field(..., description="Dotted event identifier from SSEEventType")
    execution_id: str = Field(..., description="Unique execution UUID string")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 UTC timestamp of event dispatch",
    )
    sequence: int = Field(..., ge=0, description="Strictly monotonic sequence integer")
    data: dict[str, Any] = Field(default_factory=dict, description="Sanitized payload")

    def to_sse_format(self) -> str:
        """Format as valid SSE text/event-stream wire payload."""
        import json

        payload = json.dumps(self.model_dump())
        return f"event: {self.event}\nid: {self.sequence}\ndata: {payload}\n\n"


class EventReplayResponse(BaseModel):
    """Response payload for replaying events following network disconnection."""

    model_config = ConfigDict(extra="ignore")

    execution_id: uuid.UUID
    after_sequence: int
    events: list[StreamEvent]
    total_events: int
    is_terminal: bool = False
