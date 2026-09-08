"""Pydantic schemas for the Unified AI Analyst API."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AnalystQueryRequest(BaseModel):
    """Payload for submitting a question to the Unified AI Analyst."""

    query: str = Field(..., min_length=2, max_length=2000, description="Natural language question")
    datasource_id: UUID | None = Field(
        None, description="Optional target datasource ID for structured queries"
    )
    top_k: int | None = Field(
        None, ge=1, le=50, description="Maximum evidence candidates per retrieval"
    )
    limit: int | None = Field(
        None, ge=1, le=5000, description="Maximum SQL rows returned for structured analysis"
    )


class CitationItem(BaseModel):
    """Normalized citation source referencing an evidence marker."""

    id: str = Field(..., description="Evidence citation tag, e.g. S1 or R1")
    type: str = Field(..., description="Source modality: 'sql' or 'document'")
    title: str = Field(..., description="Document title or database table name")
    is_calculated: bool = Field(
        False, description="True if mathematically derived via SQL; False if quoted"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Source provenance details")


class DataConflictItem(BaseModel):
    """Disclosed contradiction between evidence sources."""

    field: str
    source_a: str
    value_a: Any
    source_b: str
    value_b: Any
    severity: str
    description: str


class AnalystDiagnosticsResponse(BaseModel):
    """Observability timings and accounting for the query lifecycle."""

    planning_ms: float
    sql_ms: float
    rag_ms: float
    merge_ms: float
    conflict_ms: float
    generation_ms: float
    total_ms: float
    branches_executed: int
    degraded: bool = False
    degradation_reason: str | None = None


class AnalystQueryResponse(BaseModel):
    """Unified grounded response from the AI Analyst."""

    answer: str = Field(..., description="Grounded, evidence-attributed final answer")
    grounded: bool = Field(..., description="Indicates if answer is strictly grounded in evidence")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Composite system confidence score")
    routes: list[str] = Field(default_factory=list, description="Subsystem routes traversed")
    citations: list[CitationItem] = Field(
        default_factory=list, description="Referenced evidence sources"
    )
    conflicts: list[DataConflictItem] = Field(
        default_factory=list, description="Detected source discrepancies"
    )
    is_partial: bool = Field(
        False, description="True if one or more execution branches experienced partial degradation"
    )
    diagnostics: AnalystDiagnosticsResponse
