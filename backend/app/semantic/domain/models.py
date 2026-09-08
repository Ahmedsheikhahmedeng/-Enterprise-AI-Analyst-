"""Domain models and value objects for Semantic Catalog and Query Planning."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.semantic.domain.enums import (
    ConflictSeverity,
    MatchSource,
    MetricAggregation,
    SemanticObjectType,
    SemanticStatus,
)


class MetricDefinition(BaseModel):
    """High-level semantic declaration of a business metric."""

    model_config = ConfigDict(frozen=True)

    name: str
    expression: str
    grain: str | None = None
    filters: list[str] = Field(default_factory=list)
    dataset_id: uuid.UUID | None = None
    unit: str | None = None
    aggregation: MetricAggregation = MetricAggregation.SUM


class ColumnMappingItem(BaseModel):
    """Summary of a physical column mapped to a semantic object."""

    model_config = ConfigDict(frozen=True)

    mapping_id: uuid.UUID
    dataset_id: uuid.UUID
    column_id: uuid.UUID
    column_name: str
    mapping_type: str
    confidence: float
    is_verified: bool


class ResolvedMetric(BaseModel):
    """Semantic metric resolved from user input."""

    model_config = ConfigDict(frozen=True)

    metric_id: uuid.UUID
    name: str
    display_name: str | None = None
    formula: str
    aggregation: str
    dataset_id: uuid.UUID | None = None
    confidence: float = 1.0
    is_verified: bool = False
    status: SemanticStatus = SemanticStatus.PUBLISHED
    column_mappings: list[ColumnMappingItem] = Field(default_factory=list)


class ResolvedDimension(BaseModel):
    """Semantic dimension resolved from user input."""

    model_config = ConfigDict(frozen=True)

    dimension_id: uuid.UUID
    name: str
    dataset_id: uuid.UUID
    column_id: uuid.UUID
    column_name: str
    data_type: str
    confidence: float = 1.0
    status: SemanticStatus = SemanticStatus.PUBLISHED


class SemanticQueryPlan(BaseModel):
    """Deterministic, provenanced execution blueprint resolved from business concepts."""

    model_config = ConfigDict(frozen=True)

    question: str
    resolved_metrics: list[ResolvedMetric] = Field(default_factory=list)
    resolved_dimensions: list[ResolvedDimension] = Field(default_factory=list)
    resolved_entities: list[str] = Field(default_factory=list)
    dataset_id: uuid.UUID | None = None
    dataset_version_id: uuid.UUID | int | None = None
    sql_hint: str | None = None
    filters: list[str] = Field(default_factory=list)
    is_authoritative: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


class SemanticSearchResultItem(BaseModel):
    """Ranked discovery hit across business terms, metrics, dimensions, entities, and synonyms."""

    object_id: uuid.UUID
    object_type: SemanticObjectType
    name: str
    description: str | None = None
    definition: str | None = None
    status: SemanticStatus
    match_source: MatchSource
    score: float
    is_verified: bool = False
    language: str = "en"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticConflictModel(BaseModel):
    """Detected conceptual or formulaic collision between semantic objects."""

    model_config = ConfigDict(frozen=True)

    conflict_id: uuid.UUID
    organization_id: uuid.UUID
    object_type: str
    object_ids: list[str]
    severity: ConflictSeverity
    reason: str
    is_resolved: bool = False
    created_at: datetime
