"""Pydantic schemas for SQL Agent REST API endpoints."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SQLAgentRequest(BaseModel):
    """Request payload for executing structured data questions via SQL Agent."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="Natural language question to translate to SQL and execute",
    )
    datasource_id: UUID = Field(
        ...,
        description="Target DataSource or Dataset UUID belonging to the tenant",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Maximum rows to return from the SQL query",
    )
    analyze: bool = Field(
        default=True,
        description="Whether to execute Python/Pandas analytical summaries over results",
    )


class SQLQueryResultResponse(BaseModel):
    """Execution results consisting of columns and row mappings."""

    columns: list[str] = Field(..., description="Ordered column names returned by query")
    rows: list[dict[str, Any]] = Field(..., description="Row records formatted as key-value pairs")
    row_count: int = Field(..., description="Total rows returned")
    truncated: bool = Field(default=False, description="Whether rows were truncated by limits")
    duration_ms: float = Field(..., description="Execution duration in milliseconds")


class SQLProvenanceResponse(BaseModel):
    """Audit and verification provenance tracking metadata."""

    sql_hash: str = Field(..., description="Deterministic SHA-256 hash of normalized SQL")
    datasource_id: str = Field(..., description="Target data source identifier")
    tables_used: list[str] = Field(default_factory=list, description="Tables accessed by query")
    columns_used: list[str] = Field(default_factory=list, description="Columns accessed by query")
    row_count: int = Field(..., description="Row count processed")
    duration_ms: float = Field(..., description="Total execution duration in milliseconds")


class SQLAnalysisResponse(BaseModel):
    """Controlled analytical calculations computed without LLM arithmetic."""

    summary: str = Field(..., description="Textual narrative summary of the data insights")
    metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated key metrics (sum, avg, count, etc.)",
    )
    comparisons: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Relative comparisons and percentage changes",
    )
    trends: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Directional or time-series changes",
    )


class SQLAgentResponse(BaseModel):
    """Top-level structured response containing SQL, data, analysis, and provenance."""

    question: str = Field(..., description="Original user question")
    sql: str = Field(..., description="Validated read-only SQL executed")
    query_result: SQLQueryResultResponse = Field(..., description="Tabular results")
    analysis: SQLAnalysisResponse | None = Field(
        default=None,
        description="Statistical and analytical breakdown",
    )
    provenance: SQLProvenanceResponse = Field(
        ...,
        description="Audit verification and provenance record",
    )
    diagnostics: dict[str, Any] = Field(
        default_factory=dict,
        description="Operational metrics and latencies",
    )
