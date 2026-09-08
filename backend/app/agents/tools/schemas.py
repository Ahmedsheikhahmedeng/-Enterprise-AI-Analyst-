"""Typed Pydantic input schemas for all initial enterprise tools."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalystQueryInput(BaseModel):
    """Input parameters for analyst.query tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ..., min_length=3, max_length=2000, description="Natural language question to analyze"
    )
    datasource_id: uuid.UUID | None = Field(
        default=None, description="Optional target database connection ID"
    )
    limit: int | None = Field(default=None, ge=1, le=1000, description="Row limit for SQL parts")
    top_k: int | None = Field(
        default=None, ge=1, le=50, description="Document chunks limit for RAG parts"
    )


class SQLQueryInput(BaseModel):
    """Input parameters for sql.query tool."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ..., min_length=3, max_length=2000, description="Natural language analytical question"
    )
    datasource_id: uuid.UUID = Field(..., description="Target database data source ID")
    limit: int | None = Field(default=None, ge=1, le=1000)


class RAGRetrieveInput(BaseModel):
    """Input parameters for rag.retrieve tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        ..., min_length=3, max_length=2000, description="Semantic search / RAG retrieval query"
    )
    top_k: int | None = Field(default=None, ge=1, le=50)


class ReportCreateInput(BaseModel):
    """Input parameters for report.create tool."""

    model_config = ConfigDict(extra="forbid")

    analysis_run_id: uuid.UUID = Field(
        ..., description="ID of completed AnalysisRun to convert into report"
    )
    title: str = Field(..., min_length=3, max_length=255, description="Executive report title")
    subtitle: str | None = Field(default=None, max_length=255)
    template: str = Field(default="executive", max_length=50)


class EvaluationRunInput(BaseModel):
    """Input parameters for evaluation.run tool."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID = Field(..., description="Target evaluation benchmark dataset ID")
    dataset_version: int | None = Field(default=None, ge=1)
    max_cases: int | None = Field(default=None, ge=1, le=50)
    tags: list[str] | None = Field(default=None)


class DataSourceListInput(BaseModel):
    """Input parameters for datasource.list tool."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100, description="Max data sources to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class DataSourceSchemaInput(BaseModel):
    """Input parameters for datasource.schema tool."""

    model_config = ConfigDict(extra="forbid")

    datasource_id: uuid.UUID = Field(..., description="Target data source ID")
    refresh: bool = Field(default=False, description="Force refresh cache")


class DataSourcePreviewInput(BaseModel):
    """Input parameters for datasource.preview tool."""

    model_config = ConfigDict(extra="forbid")

    datasource_id: uuid.UUID = Field(..., description="Target data source ID")
    table_or_sheet: str | None = Field(default=None, description="Table name or sheet name")
    limit: int = Field(default=20, ge=1, le=100, description="Max sample rows")


class DataSourceQueryInput(BaseModel):
    """Input parameters for datasource.query tool."""

    model_config = ConfigDict(extra="forbid")

    datasource_id: uuid.UUID = Field(..., description="Target data source ID")
    query: str = Field(..., min_length=1, max_length=20000, description="Query string")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    timeout_ms: int = Field(default=5000, ge=100, le=60000, description="Execution timeout in ms")
    max_rows: int = Field(default=1000, ge=1, le=5000, description="Maximum rows returned")


class DatasetListInput(BaseModel):
    """Input parameters for dataset.list tool."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100, description="Max datasets to return")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class DatasetGetInput(BaseModel):
    """Input parameters for dataset.get tool."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID = Field(..., description="Target dataset ID")


class DatasetProfileInput(BaseModel):
    """Input parameters for dataset.profile tool."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID = Field(..., description="Target dataset ID")


class DatasetVersionsInput(BaseModel):
    """Input parameters for dataset.versions tool."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID = Field(..., description="Target dataset ID")


class DatasetQualityInput(BaseModel):
    """Input parameters for dataset.quality tool."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID = Field(..., description="Target dataset ID")


class SemanticSearchInput(BaseModel):
    """Input parameters for semantic.search tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=255, description="Search query string")
    limit: int = Field(default=10, ge=1, le=50, description="Max results to return")
    object_types: list[str] | None = Field(default=None, description="Filter by object types")


class SemanticGetTermInput(BaseModel):
    """Input parameters for semantic.get_term tool."""

    model_config = ConfigDict(extra="forbid")

    term_id: uuid.UUID = Field(..., description="Target business term ID")


class SemanticResolveMetricInput(BaseModel):
    """Input parameters for semantic.resolve_metric tool."""

    model_config = ConfigDict(extra="forbid")

    metric_name: str = Field(
        ..., min_length=1, max_length=255, description="Name of metric to resolve"
    )
    dataset_id: uuid.UUID | None = Field(default=None, description="Optional target dataset ID")


class SemanticResolveDimensionInput(BaseModel):
    """Input parameters for semantic.resolve_dimension tool."""

    model_config = ConfigDict(extra="forbid")

    dimension_name: str = Field(
        ..., min_length=1, max_length=255, description="Name of dimension to resolve"
    )
    dataset_id: uuid.UUID | None = Field(default=None, description="Optional target dataset ID")


class SemanticGetEntityInput(BaseModel):
    """Input parameters for semantic.get_entity tool."""

    model_config = ConfigDict(extra="forbid")

    entity_id: uuid.UUID = Field(..., description="Target semantic entity ID")


class SemanticGetRelationshipsInput(BaseModel):
    """Input parameters for semantic.get_relationships tool."""

    model_config = ConfigDict(extra="forbid")

    entity_id: uuid.UUID | None = Field(
        default=None, description="Optional entity ID to filter relationships"
    )


class SemanticGetQueryPlanInput(BaseModel):
    """Input parameters for semantic.get_query_plan tool."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        ..., min_length=1, max_length=500, description="Natural language analytical question"
    )
    dataset_id: uuid.UUID | None = Field(default=None, description="Optional target dataset ID")


# ---------------------------------------------------------------------------
# Knowledge Graph & Relationship Reasoning Tools (TASK 29)
# ---------------------------------------------------------------------------


class GraphSearchInput(BaseModel):
    """Input parameters for graph.search tool."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=500, description="Concept or entity text")
    node_type: str | None = Field(default=None, description="Optional node type filter")
    limit: int = Field(default=10, ge=1, le=100)


class GraphGetNodeInput(BaseModel):
    """Input parameters for graph.get_node tool."""

    model_config = ConfigDict(extra="forbid")

    node_id: uuid.UUID = Field(..., description="Target knowledge graph vertex ID")


class GraphGetNeighborsInput(BaseModel):
    """Input parameters for graph.get_neighbors tool."""

    model_config = ConfigDict(extra="forbid")

    node_id: uuid.UUID = Field(..., description="Target knowledge graph vertex ID")
    depth: int = Field(default=1, ge=1, le=4, description="Neighborhood depth (max 4)")
    edge_types: list[str] | None = Field(default=None, description="Optional edge types filter")


class GraphFindPathInput(BaseModel):
    """Input parameters for graph.find_path tool."""

    model_config = ConfigDict(extra="forbid")

    start_node_id: uuid.UUID = Field(..., description="Originating vertex ID")
    target_node_id: uuid.UUID = Field(..., description="Destination vertex ID")
    max_depth: int = Field(default=4, ge=1, le=4, description="Maximum hops (max 4)")
    only_verified: bool = Field(default=False, description="Filter for verified edges only")


class GraphQueryInput(BaseModel):
    """Input parameters for graph.query tool."""

    model_config = ConfigDict(extra="forbid")

    start_entity: str | None = Field(default=None, description="Start entity name or mention")
    target_concept: str | None = Field(
        default=None, description="Target concept, metric, or dimension"
    )
    max_depth: int = Field(default=3, ge=1, le=4)


class GraphGetLineageInput(BaseModel):
    """Input parameters for graph.get_lineage tool."""

    model_config = ConfigDict(extra="forbid")

    node_id: uuid.UUID = Field(..., description="Root vertex ID for lineage trace")
    direction: str = Field(default="FORWARD", description="Lineage direction: FORWARD or REVERSE")
    max_depth: int = Field(default=4, ge=1, le=4)
