"""Pydantic schemas for Evaluation REST API requests and responses."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreateEvaluationDatasetRequest(BaseModel):
    """Payload to initialize a new evaluation benchmark dataset."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    language: str = Field("en", min_length=2, max_length=20)


class EvaluationDatasetResponse(BaseModel):
    """Metadata response for an evaluation dataset."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    description: str | None
    language: str
    version: int
    status: str
    created_at: datetime
    updated_at: datetime


class EvaluationDatasetListResponse(BaseModel):
    """Paginated collection of evaluation datasets."""

    items: list[EvaluationDatasetResponse]
    total: int
    page: int
    page_size: int


class CreateEvaluationCaseRequest(BaseModel):
    """Payload to add a ground-truth benchmark case to an evaluation dataset."""

    query: str = Field(..., min_length=1)
    route_expected: str = Field(..., description="Expected route: 'rag', 'sql', 'hybrid', 'none'")
    language: str = "en"
    datasource_id: UUID | None = None
    expected_answer: str | None = None
    expected_citations: list[str] = Field(default_factory=list)
    expected_documents: list[str] = Field(default_factory=list)
    expected_sql_semantics: str | None = None
    expected_metrics: dict[str, Any] = Field(default_factory=dict)
    expected_rows: list[dict[str, Any]] = Field(default_factory=list)
    relevant_chunks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: str = "medium"
    enabled: bool = True


class EvaluationCaseResponse(BaseModel):
    """Response structure for an individual evaluation case."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    organization_id: UUID
    version: int
    query: str
    route_expected: str
    language: str
    datasource_id: UUID | None
    expected_answer: str | None
    expected_citations: list[str]
    expected_documents: list[str]
    expected_metrics: dict[str, Any]
    difficulty: str
    enabled: bool
    created_at: datetime


class EvaluationCaseListResponse(BaseModel):
    """Collection of evaluation cases."""

    items: list[EvaluationCaseResponse]
    total: int


class StartEvaluationRunRequest(BaseModel):
    """Payload to trigger a benchmark evaluation run."""

    dataset_id: UUID
    dataset_version: int | None = None
    max_cases: int | None = None
    tags: list[str] | None = None


class EvaluationRunResponse(BaseModel):
    """Response structure for an evaluation benchmark run."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    dataset_id: UUID
    dataset_version: int
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    duration_ms: float
    started_at: datetime | None
    completed_at: datetime | None
    git_commit: str


class EvaluationCaseResultResponse(BaseModel):
    """Granular metric scores and status for a single evaluated case."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    case_id: UUID
    actual_route: str | None
    expected_route: str | None
    passed: bool
    failure_reason: str | None
    retrieval_score: float
    rag_score: float
    sql_score: float
    grounding_score: float
    citation_score: float
    hallucination_score: float
    latency_ms: float
    estimated_cost: float
    metrics_detail: dict[str, Any]


class CompareEvaluationRunsRequest(BaseModel):
    """Payload requesting regression comparison between a candidate and baseline run."""

    baseline_run_id: UUID


class ScorecardResponse(BaseModel):
    """Aggregate quality and performance scorecard response."""

    run_id: str
    dataset_id: str
    dataset_version: int
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    metrics: dict[str, float]
    latency: dict[str, float]
    cost: dict[str, float]
    segmented_scores: dict[str, float]


class RegressionReportResponse(BaseModel):
    """Regression detection outcome comparing two benchmark runs."""

    baseline_run_id: str
    candidate_run_id: str
    status: str
    deltas: dict[str, float]
    new_failures_count: int
    new_failures: list[str]
    regressions: list[dict[str, Any]]
