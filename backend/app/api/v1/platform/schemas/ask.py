"""Ask Request and Response Schemas — TASK 34."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.platform.schemas.evidence import CitationItem
from app.api.v1.platform.schemas.execution import ApprovalUIContract


class AskRequest(BaseModel):
    """Canonical request payload for querying the Enterprise AI Platform."""

    model_config = ConfigDict(extra="ignore")

    question: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="The natural language question or analytical query to execute.",
    )
    conversation_id: uuid.UUID | None = Field(
        default=None,
        description="Optional conversation thread identifier to append query context.",
    )
    mode: str = Field(
        default="AUTO",
        description="Execution mode: 'AUTO', 'FAST', 'DEEP', 'VERIFIED'.",
    )
    response_style: str = Field(
        default="STANDARD",
        description="Style of synthesized response: 'CONCISE', 'STANDARD', 'EXECUTIVE', 'TECHNICAL'.",
    )
    stream: bool = Field(
        default=True,
        description="If True, begins asynchronous execution and returns streaming SSE URL. If False, awaits completion.",
    )
    target_dataset_id: uuid.UUID | None = Field(
        default=None,
        description="Optional dataset constraint for SQL execution.",
    )
    enable_clarification: bool = Field(
        default=True,
        description="Whether to ask clarifying questions when ambiguous entities or metrics are detected.",
    )


class AskResponseData(BaseModel):
    """Final verified response data returned when stream=False."""

    model_config = ConfigDict(extra="ignore")

    execution_id: uuid.UUID
    answer: str
    status: str
    decision: str
    confidence_score: float
    evidence_coverage: float
    citations: list[CitationItem] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clarification_prompt: str | None = None
    approval: ApprovalUIContract | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class AsyncAskResponseData(BaseModel):
    """Initial payload returned when stream=True to initiate SSE streaming."""

    model_config = ConfigDict(extra="ignore")

    execution_id: uuid.UUID
    status: str = "RECEIVED"
    stream_url: str
    events_url: str
    created_at: str
