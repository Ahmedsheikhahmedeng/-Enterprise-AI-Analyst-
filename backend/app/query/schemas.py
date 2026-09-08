"""Pydantic schemas for Query Understanding endpoints and serialization."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.query.models import QueryIntent


class QueryAnalysisRequest(BaseModel):
    """Request payload for dedicated query analysis and planning."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Raw natural language search query to analyze and plan",
    )
    enable_rewrite: bool = Field(
        default=True,
        description="Whether to generate a search-optimized rewrite for ambiguous queries",
    )
    enable_expansion: bool = Field(
        default=True,
        description="Whether to generate synonym and domain alternative queries",
    )
    enable_decomposition: bool = Field(
        default=True,
        description="Whether to decompose complex/comparative queries into sub-queries",
    )
    max_alternatives: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Optional override for maximum alternative queries",
    )
    max_subqueries: int | None = Field(
        default=None,
        ge=1,
        le=10,
        description="Optional override for maximum decomposed sub-queries",
    )


class ExtractedEntityResponse(BaseModel):
    """Structured representation of an extracted entity."""

    name: str
    category: str
    value: Any
    is_explicit: bool
    confidence: float


class QueryDiagnosticsResponse(BaseModel):
    """Latency and observability metadata for query understanding."""

    language_latency_ms: float
    normalization_latency_ms: float
    intent_latency_ms: float
    entity_latency_ms: float
    rewrite_latency_ms: float
    expansion_latency_ms: float
    decomposition_latency_ms: float
    total_understanding_ms: float
    provider: str
    model: str
    tokens_used: int
    cost_usd: float
    is_degraded: bool
    degradation_reason: str | None


class SearchPlanResponse(BaseModel):
    """Complete structured SearchPlan returned by the analysis API."""

    original_query: str
    primary_query: str
    alternative_queries: list[str]
    sub_queries: list[str]
    language: str
    detected_languages: list[str]
    intent: QueryIntent
    entities: list[ExtractedEntityResponse]
    hard_filters: dict[str, Any]
    soft_filters: dict[str, Any]
    confidence: float
    diagnostics: QueryDiagnosticsResponse


class QueryAnalysisResponse(BaseModel):
    """Standardized top-level response container for query analysis endpoint."""

    search_plan: SearchPlanResponse
