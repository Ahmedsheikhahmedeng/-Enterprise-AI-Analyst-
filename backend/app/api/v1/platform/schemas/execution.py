"""Execution, Stage Progress, History and Approval Schemas — TASK 34."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.platform.schemas.evidence import CitationItem


class StageProgress(BaseModel):
    """Detailed progress status for an individual reasoning stage."""

    model_config = ConfigDict(extra="ignore")

    stage: str = Field(..., description="Stage name e.g. 'UNDERSTANDING', 'SEMANTIC', 'SQL'")
    status: str = Field(
        ..., description="Stage status: 'PENDING', 'RUNNING', 'COMPLETED', 'FAILED'"
    )
    progress: int = Field(0, ge=0, le=100, description="Cumulative progress percentage")
    started_at: str | None = None
    completed_at: str | None = None


class ExecutionSummary(BaseModel):
    """Brief metadata summary for execution history list queries."""

    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    query: str
    status: str
    mode: str
    decision: str
    confidence_score: float
    evidence_coverage: float
    created_at: datetime
    completed_at: datetime | None = None


class ExecutionDetail(BaseModel):
    """Full execution payload representation."""

    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID
    query: str
    status: str
    mode: str
    execution_strategy: str
    decision: str
    confidence_score: float
    evidence_coverage: float
    answer: str | None = None
    clarification_prompt: str | None = None
    citations: list[CitationItem] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime | None = None


class CancellationResponse(BaseModel):
    """Response payload when an in-flight execution is cancelled."""

    model_config = ConfigDict(extra="ignore")

    execution_id: uuid.UUID
    previous_status: str
    current_status: str
    cancelled_at: str


class ApprovalUIContract(BaseModel):
    """Clean approval contract presented to frontend users without leaking internal governance rules."""

    model_config = ConfigDict(extra="ignore")

    approval_required: bool
    approval_request_id: str | None = None
    risk_level: str | None = None
    expires_at: str | None = None
    required_approvers: int = 1
    status: str = "PENDING"
