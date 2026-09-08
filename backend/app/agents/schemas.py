"""Pydantic schemas and serialization contracts for Agent API and execution."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentStatus(StrEnum):
    """Explicit lifecycle status states of an AgentSession."""

    CREATED = "created"
    PLANNING = "planning"
    PLANNED = "planned"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BUDGET_EXCEEDED = "budget_exceeded"


class AgentType(StrEnum):
    """Supported agent profile types."""

    ANALYST_AGENT = "analyst_agent"
    RESEARCH_AGENT = "research_agent"
    REPORT_AGENT = "report_agent"
    EVALUATION_AGENT = "evaluation_agent"


class ToolRiskLevel(StrEnum):
    """Risk tier of registered tools."""

    READ = "read"
    SAFE_WRITE = "safe_write"
    SENSITIVE = "sensitive"
    HIGH_RISK = "high_risk"


class ApprovalStatus(StrEnum):
    """State of an operator sign-off request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ---------------------------------------------------------------------------
# API Request / Response Schemas
# ---------------------------------------------------------------------------


class AgentSessionCreateRequest(BaseModel):
    """Request payload to initialize an agent session."""

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(
        ..., min_length=3, max_length=2000, description="Analytical goal or task for agent"
    )
    agent_type: AgentType = Field(
        default=AgentType.ANALYST_AGENT, description="Type of agent profile to use"
    )
    datasource_id: uuid.UUID | None = Field(
        default=None, description="Target data source ID if structured query"
    )
    max_steps: int | None = Field(
        default=None, ge=1, le=50, description="Override maximum allowed steps"
    )
    max_tokens: int | None = Field(default=None, ge=100, le=200000)
    max_cost_usd: float | None = Field(default=None, ge=0.01, le=50.0)


class AgentStepSchema(BaseModel):
    """Specification of a single plan step."""

    step_id: str = Field(..., description="Unique step identifier within plan")
    sequence: int = Field(..., ge=1)
    tool_name: str = Field(..., description="Name of registered tool to call")
    tool_input: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(..., max_length=500, description="Concise action rationale (NO CoT)")
    estimated_cost: float = Field(default=0.0, ge=0.0)
    estimated_duration: float = Field(default=0.0, ge=0.0)
    requires_approval: bool = Field(default=False)


class AgentPlanResponse(BaseModel):
    """Structured execution plan response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    goal: str
    steps: list[AgentStepSchema]
    estimated_cost: float
    estimated_tokens: int
    estimated_duration: float
    requires_approval: bool
    created_at: datetime


class AgentStepResponse(BaseModel):
    """Persisted step execution record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    sequence: int
    tool_name: str
    tool_input: dict[str, Any]
    reason: str
    status: str
    output: dict[str, Any] | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    cost: float = 0.0
    tokens: int = 0
    duration_ms: float = 0.0
    requires_approval: bool = False
    created_at: datetime
    completed_at: datetime | None = None


class ApprovalResponse(BaseModel):
    """Approval request details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    step_id: uuid.UUID
    organization_id: uuid.UUID
    requested_by: uuid.UUID | None = None
    approved_by: uuid.UUID | None = None
    status: str
    reason: str
    created_at: datetime
    resolved_at: datetime | None = None


class ApprovalDecisionRequest(BaseModel):
    """Decision payload for approve/reject endpoints."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(default="", max_length=500, description="Operator explanation or comments")


class AgentSessionResponse(BaseModel):
    """Agent session summary and lifecycle state."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by: uuid.UUID | None = None
    status: str
    agent_type: str
    goal: str
    plan_id: uuid.UUID | None = None
    current_step: int
    max_steps: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    final_answer: dict[str, Any] | None = None
    total_tokens: int
    total_cost: float
    duration_ms: float


class AgentFinalAnswerResponse(BaseModel):
    """Typed final synthesized answer representation."""

    session_id: uuid.UUID
    status: str
    answer: str
    steps: int
    tools_used: list[str]
    citations: list[str]
    grounded: bool
    degraded: bool
    usage: dict[str, Any]
