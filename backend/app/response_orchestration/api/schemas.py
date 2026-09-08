"""Pydantic request and response schemas for Response Orchestration REST API."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.response_orchestration.domain.enums import (
    DecisionType,
    EvidenceTrustLevel,
    OrchestrationMode,
    OrchestrationStatus,
    ResponseStyle,
)


class EnterpriseAskRequest(BaseModel):
    """Client request schema for canonical enterprise query execution."""

    question: str = Field(
        ..., min_length=2, max_length=2000, description="Natural language question"
    )
    conversation_id: uuid.UUID | None = Field(
        default=None, description="Optional conversation context thread ID"
    )
    mode: OrchestrationMode = Field(
        default=OrchestrationMode.AUTO, description="Execution routing mode"
    )
    response_style: ResponseStyle = Field(
        default=ResponseStyle.STANDARD, description="Answer tone and granularity"
    )
    target_dataset_id: uuid.UUID | None = Field(
        default=None, description="Optional focused dataset ID"
    )
    enable_clarification: bool = Field(
        default=True, description="Enable interactive clarification for ambiguous terms"
    )

    model_config = ConfigDict(extra="forbid")


class CitationItemSchema(BaseModel):
    """Citation metadata schema."""

    citation_id: str
    source_type: str
    source_id: str
    title: str
    snippet: str
    trust_level: EvidenceTrustLevel


class ConflictItemSchema(BaseModel):
    """Detected evidence discrepancy schema."""

    conflict_id: str
    field: str
    source_a: str
    value_a: Any
    source_b: str
    value_b: Any
    severity: str
    description: str
    resolved_value: Any | None = None


class EnterpriseAskResponse(BaseModel):
    """Canonical enterprise query response schema."""

    execution_id: uuid.UUID
    request_id: uuid.UUID
    trace_id: str
    answer: str
    status: OrchestrationStatus
    decision: DecisionType
    confidence_score: float
    evidence_coverage: float
    citations: list[CitationItemSchema] = Field(default_factory=list)
    conflicts: list[ConflictItemSchema] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clarification_prompt: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class OrchestrationPreviewResponse(BaseModel):
    """Preview of planning and routing without executing expensive synthesis."""

    strategy: str
    resolved_metrics: list[str]
    resolved_dimensions: list[str]
    requires_clarification: bool
    clarification_options: list[str] = Field(default_factory=list)
