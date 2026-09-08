"""Pydantic schemas for Governance & Human-in-the-Loop HTTP API."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.governance.domain.enums import ApprovalType


class ApprovalRequestCreate(BaseModel):
    """Payload to initiate an approval request for a sensitive operation."""

    request_type: ApprovalType
    resource_type: str = Field(..., min_length=1, max_length=100)
    resource_id: str | None = Field(default=None, max_length=255)
    action_payload: Any = None
    reason: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    risk_factors: dict[str, Any] = Field(default_factory=dict)


class VoteRequest(BaseModel):
    """Payload to cast a vote on an approval request."""

    comment: str | None = None


class ReviewCommentCreate(BaseModel):
    """Payload to add a review comment."""

    comment: str = Field(..., min_length=1)


class VoteResponse(BaseModel):
    """Reviewer vote detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reviewer_id: UUID
    decision: str
    comment: str | None = None
    created_at: datetime | None = None


class CommentResponse(BaseModel):
    """Discussion comment detail."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    author_id: UUID
    comment: str
    created_at: datetime | None = None


class DecisionResponse(BaseModel):
    """Immutable resolution record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    decision: str
    reviewer_ids: list[str]
    policy_version: int
    risk_score: float
    decision_hash: str
    created_at: datetime | None = None


class ApprovalRequestResponse(BaseModel):
    """Full detail of a governed approval request."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    request_type: str
    requester_id: UUID
    resource_type: str
    resource_id: str | None = None
    risk_level: str
    risk_score: float
    status: str
    reason: str | None = None
    action_hash: str | None = None
    resource_hash: str | None = None
    policy_version: int
    expires_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
    votes: list[VoteResponse] = Field(default_factory=list)
    comments: list[CommentResponse] = Field(default_factory=list)


class GovernancePolicyResponse(BaseModel):
    """Tenant governance policy definition."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    policy_version: int
    rules: dict[str, Any]
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolicyUpdateRequest(BaseModel):
    """Payload to submit updated governance rules."""

    rules: dict[str, Any]
