"""Pydantic schemas and enums for Enterprise Agent Memory."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(StrEnum):
    """Categorization of agent memory by permanence and role."""

    SHORT_TERM = "short_term"
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


class MemoryVisibility(StrEnum):
    """Access boundary of a memory item."""

    PRIVATE = "private"  # only creator can view
    USER = "user"  # creator across all sessions
    ORGANIZATION = "organization"  # members of the organization
    SESSION = "session"  # confined to single session


class MemoryPrivacyLevel(StrEnum):
    """Sensitivity classification governing redaction and access."""

    NORMAL = "normal"
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class MemoryStatus(StrEnum):
    """Lifecycle status of a memory item."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    STALE = "stale"
    DELETED = "deleted"


class MemorySourceType(StrEnum):
    """Provenance origin of the memory item."""

    USER_DECLARED = "user_declared"
    AGENT_DERIVED = "agent_derived"
    DOCUMENT_DERIVED = "document_derived"
    SYSTEM_VERIFIED = "system_verified"


class MemoryCandidate(BaseModel):
    """Unpersisted candidate extracted from dialog, tool output, or user input."""

    model_config = ConfigDict(extra="forbid")

    memory_type: MemoryType = MemoryType.SEMANTIC
    content: str = Field(..., min_length=3, max_length=10000)
    summary: str | None = Field(default=None, max_length=1000)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    source_type: MemorySourceType = MemorySourceType.AGENT_DERIVED
    source_id: str | None = None
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    visibility: MemoryVisibility = MemoryVisibility.ORGANIZATION
    privacy_level: MemoryPrivacyLevel = MemoryPrivacyLevel.NORMAL
    supersedes_memory_id: uuid.UUID | None = None


class MemoryItemCreateRequest(BaseModel):
    """API payload for explicitly declaring or recording a memory item."""

    model_config = ConfigDict(extra="forbid")

    memory_type: MemoryType = Field(default=MemoryType.SEMANTIC)
    content: str = Field(..., min_length=3, max_length=10000)
    summary: str | None = Field(default=None, max_length=1000)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    visibility: MemoryVisibility = Field(default=MemoryVisibility.ORGANIZATION)
    privacy_level: MemoryPrivacyLevel = Field(default=MemoryPrivacyLevel.NORMAL)
    session_id: uuid.UUID | None = None
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    supersedes_memory_id: uuid.UUID | None = None


class MemoryItemUpdateRequest(BaseModel):
    """API payload for updating an existing memory item (creates new version)."""

    model_config = ConfigDict(extra="forbid")

    content: str | None = Field(default=None, min_length=3, max_length=10000)
    summary: str | None = Field(default=None, max_length=1000)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    visibility: MemoryVisibility | None = None
    privacy_level: MemoryPrivacyLevel | None = None


class MemoryItemResponse(BaseModel):
    """Detailed representation of a stored memory item."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID | None
    session_id: uuid.UUID | None
    memory_type: MemoryType
    content: str
    summary: str | None
    importance: float
    confidence: float
    source_type: MemorySourceType
    source_id: str | None
    source_refs: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    version: int
    content_hash: str
    visibility: MemoryVisibility
    privacy_level: MemoryPrivacyLevel
    status: MemoryStatus
    supersedes_memory_id: uuid.UUID | None
    deleted_at: datetime | None


class MemorySearchRequest(BaseModel):
    """Search request payload for semantic and metadata memory retrieval."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    memory_types: list[MemoryType] | None = None
    session_id: uuid.UUID | None = None
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    min_importance: float | None = Field(default=None, ge=0.0, le=1.0)


class MemorySearchResultItem(BaseModel):
    """Individual search result hit with calculated relevance and score breakdown."""

    memory: MemoryItemResponse
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class MemorySearchResponse(BaseModel):
    """Container response for memory search queries."""

    query: str
    total_found: int
    results: list[MemorySearchResultItem]


class MemorySummaryResponse(BaseModel):
    """High-level summary counts of active memory items for an organization."""

    organization_id: uuid.UUID
    total_memories: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    by_privacy: dict[str, int]
