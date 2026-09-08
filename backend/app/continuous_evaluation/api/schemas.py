"""Pydantic schemas for Continuous AI Evaluation, Benchmarking & Quality Monitoring."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.continuous_evaluation.domain.enums import (
    EvaluationTarget,
    QualityGateDecision,
    RegressionSeverity,
    SamplingStrategy,
)


class BenchmarkCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    task_type: str = Field(..., max_length=50)  # RAG, SQL, AGENT, etc.
    target: EvaluationTarget = EvaluationTarget.END_TO_END
    dataset_id: uuid.UUID
    version: int = Field(default=1, ge=1)


class BenchmarkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None = None
    task_type: str
    target: str
    dataset_id: uuid.UUID
    version: int
    baseline_run_id: uuid.UUID | None = None
    status: str
    created_at: datetime | None = None


class BaselineUpdateRequest(BaseModel):
    baseline_run_id: uuid.UUID


class EvaluationSuiteCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    benchmark_ids: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)


class EvaluationSuiteResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None = None
    benchmark_ids: list[str]
    version: int
    status: str
    created_at: datetime | None = None


class QualityGateRuleSchema(BaseModel):
    metric_name: str
    min_threshold: float | None = None
    max_threshold: float | None = None
    max_drop_percentage: float | None = None
    is_critical: bool = False


class QualityGateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    rules: list[QualityGateRuleSchema]


class QualityGateResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None = None
    rules: dict[str, Any]
    status: str
    created_at: str | None = None


class QualityGateEvaluateRequest(BaseModel):
    gate_id: uuid.UUID
    run_id: uuid.UUID
    scorecard: dict[str, Any]


class QualityGateResultResponse(BaseModel):
    gate_id: uuid.UUID
    run_id: uuid.UUID
    decision: QualityGateDecision
    scorecard: dict[str, Any]
    violations: list[dict[str, Any]]


class RegressionFindingResponse(BaseModel):
    benchmark_id: uuid.UUID
    run_id: uuid.UUID
    baseline_run_id: uuid.UUID
    metric_name: str
    baseline_value: float
    current_value: float
    drop_percentage: float
    severity: RegressionSeverity
    details: dict[str, Any]
    is_statistically_significant: bool
    p_value: float | None = None


class CalibrationBucketResponse(BaseModel):
    bin_start: float
    bin_end: float
    avg_confidence: float
    accuracy: float
    sample_count: int


class CalibrationAnalysisResponse(BaseModel):
    run_id: uuid.UUID
    ece: float
    brier_score: float
    buckets: list[CalibrationBucketResponse]


class ProductionSampleCreateRequest(BaseModel):
    query: str
    response: str
    sampling_strategy: SamplingStrategy = SamplingStrategy.RANDOM
    data_sensitivity: str = "INTERNAL"
    retention_days: int = Field(default=30, ge=1, le=365)
    source_execution_id: str | None = None


class ProductionSampleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    query: str
    response: str
    sampling_strategy: str
    data_sensitivity: str
    redacted: bool
    expires_at: datetime
    source_execution_id: str | None = None
    created_at: datetime | None = None


class HumanEvaluationCreateRequest(BaseModel):
    evaluator_id: uuid.UUID
    accuracy_score: float = Field(..., ge=1.0, le=5.0)
    helpfulness_score: float = Field(..., ge=1.0, le=5.0)
    grounding_score: float = Field(..., ge=1.0, le=5.0)
    clarity_score: float = Field(..., ge=1.0, le=5.0)
    sample_id: uuid.UUID | None = None
    case_result_id: uuid.UUID | None = None
    comments: str | None = None


class HumanEvaluationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    evaluator_id: uuid.UUID
    sample_id: uuid.UUID | None = None
    case_result_id: uuid.UUID | None = None
    accuracy_score: float
    helpfulness_score: float
    grounding_score: float
    clarity_score: float
    normalized_score: float
    comments: str | None = None
    evaluation_source: str
    created_at: datetime | None = None


class ComparisonRequest(BaseModel):
    comparison_type: str = Field(default="MODEL")  # MODEL, PROMPT, SEMANTIC, GRAPH
    baseline_id: str
    candidate_id: str
    baseline_scorecard: dict[str, Any]
    candidate_scorecard: dict[str, Any]


class ComparisonResponse(BaseModel):
    comparison_type: str
    baseline_id: str
    candidate_id: str
    metrics_diff: dict[str, dict[str, float]]
    winner: str | None = None
    summary: str
