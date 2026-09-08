"""Pydantic request and response schemas for Semantic Catalog and Semantic Layer APIs."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.semantic.domain.enums import (
    MappingType,
    MetricAggregation,
    RelationshipType,
    SemanticObjectType,
    SemanticStatus,
)


class SemanticSearchRequest(BaseModel):
    """Request schema for hybrid semantic search."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=255, description="Search query string")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")
    object_types: list[str] | None = Field(default=None, description="Filter by object types")
    only_published: bool = Field(default=True, description="Filter by published status")


class SemanticSearchResultResponse(BaseModel):
    """Ranked search hit in semantic catalog."""

    object_id: uuid.UUID
    object_type: str
    name: str
    description: str | None = None
    definition: str | None = None
    status: str
    match_source: str
    score: float
    is_verified: bool = False
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticSearchResponse(BaseModel):
    """Response wrapper for semantic search."""

    results: list[SemanticSearchResultResponse]
    count: int


class BusinessTermCreateRequest(BaseModel):
    """Request schema to declare a new business term."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    definition: str = Field(..., min_length=1)
    description: str | None = None
    category: str | None = None
    owner: str | None = None
    steward: str | None = None


class BusinessTermUpdateRequest(BaseModel):
    """Request schema to update business term properties or definition."""

    model_config = ConfigDict(extra="forbid")

    definition: str | None = None
    description: str | None = None
    category: str | None = None
    owner: str | None = None
    steward: str | None = None


class BusinessTermVersionResponse(BaseModel):
    """Schema representing an immutable definition version of a business term."""

    id: uuid.UUID
    version: int
    definition: str
    description: str | None
    created_at: datetime


class BusinessTermResponse(BaseModel):
    """Response schema for business glossary terms."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    normalized_name: str
    definition: str
    description: str | None
    category: str | None
    status: str
    version: int
    owner: str | None
    steward: str | None
    created_at: datetime
    updated_at: datetime
    versions: list[BusinessTermVersionResponse] = Field(default_factory=list)


class SemanticMetricCreateRequest(BaseModel):
    """Request schema to declare a new semantic metric."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    definition: str = Field(..., min_length=1)
    formula: str = Field(..., min_length=1, max_length=500)
    aggregation: MetricAggregation = MetricAggregation.SUM
    display_name: str | None = None
    description: str | None = None
    grain: str | None = None
    filters: list[str] | None = None
    unit: str | None = None
    dataset_id: uuid.UUID | None = None


class SemanticMetricResponse(BaseModel):
    """Response schema for semantic metrics."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    normalized_name: str
    display_name: str | None
    description: str | None
    definition: str
    formula: str
    aggregation: str
    grain: str | None
    filters: list[str]
    unit: str | None
    dataset_id: uuid.UUID | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class SemanticDimensionCreateRequest(BaseModel):
    """Request schema to declare an analytical dimension."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID
    column_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    data_type: str = Field(..., min_length=1, max_length=50)
    description: str | None = None
    hierarchy: list[str] | None = None


class SemanticDimensionResponse(BaseModel):
    """Response schema for semantic dimensions."""

    id: uuid.UUID
    organization_id: uuid.UUID
    dataset_id: uuid.UUID
    column_id: uuid.UUID
    name: str
    normalized_name: str
    description: str | None
    data_type: str
    hierarchy: list[str]
    status: str
    created_at: datetime


class SemanticEntityCreateRequest(BaseModel):
    """Request schema to declare a business entity."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    primary_key: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    display_name_column: str | None = None


class SemanticEntityResponse(BaseModel):
    """Response schema for semantic entities."""

    id: uuid.UUID
    organization_id: uuid.UUID
    dataset_id: uuid.UUID
    name: str
    normalized_name: str
    primary_key: str
    display_name_column: str | None
    description: str | None
    status: str
    created_at: datetime


class SemanticRelationshipCreateRequest(BaseModel):
    """Request schema to define an entity relationship."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    from_entity_id: uuid.UUID
    to_entity_id: uuid.UUID
    relationship_type: RelationshipType
    from_column: str = Field(..., min_length=1, max_length=100)
    to_column: str = Field(..., min_length=1, max_length=100)


class SemanticRelationshipResponse(BaseModel):
    """Response schema for entity relationships."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    from_entity_id: uuid.UUID
    to_entity_id: uuid.UUID
    relationship_type: str
    from_column: str
    to_column: str
    status: str
    created_at: datetime


class SemanticMappingCreateRequest(BaseModel):
    """Request schema to bind physical column to semantic concept."""

    model_config = ConfigDict(extra="forbid")

    semantic_object_type: SemanticObjectType
    semantic_object_id: uuid.UUID
    dataset_id: uuid.UUID
    column_id: uuid.UUID
    dataset_version_id: uuid.UUID | None = None
    mapping_type: MappingType = MappingType.DIRECT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SemanticMappingResponse(BaseModel):
    """Response schema for column bindings."""

    id: uuid.UUID
    organization_id: uuid.UUID
    semantic_object_type: str
    semantic_object_id: uuid.UUID
    dataset_id: uuid.UUID
    column_id: uuid.UUID
    mapping_type: str
    confidence: float
    is_verified: bool
    verified_by: uuid.UUID | None
    verified_at: datetime | None
    created_at: datetime


class SemanticPublishRequest(BaseModel):
    """Request schema to advance publishing lifecycle state."""

    model_config = ConfigDict(extra="forbid")

    object_type: SemanticObjectType
    target_status: SemanticStatus = SemanticStatus.PUBLISHED


class SemanticQueryPlanRequest(BaseModel):
    """Request schema to resolve question into semantic query plan."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=500)
    dataset_id: uuid.UUID | None = None


class SemanticQueryPlanResponse(BaseModel):
    """Response schema representing provenanced semantic execution plan."""

    question: str
    is_authoritative: bool
    dataset_id: uuid.UUID | None
    sql_hint: str | None
    resolved_metrics: list[dict[str, Any]]
    resolved_dimensions: list[dict[str, Any]]
    provenance: dict[str, Any]


class SemanticConflictResponse(BaseModel):
    """Response schema representing detected semantic collisions."""

    id: uuid.UUID
    organization_id: uuid.UUID
    object_type: str
    object_ids: list[str]
    severity: str
    reason: str
    is_resolved: bool
    created_at: datetime
