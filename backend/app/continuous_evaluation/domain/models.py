"""Domain models and value objects for Enterprise Continuous AI Evaluation."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.continuous_evaluation.domain.enums import (
    DifficultyLevel,
    EvaluationSource,
    EvaluationTarget,
    MetricDirection,
    QualityGateDecision,
    RegressionSeverity,
    SamplingStrategy,
)


@dataclass(frozen=True)
class SystemVersionInfo:
    """Version metadata ensuring reproducible, auditable evaluation runs."""

    system_version: str = "1.0.0"
    code_version: str = "HEAD"
    model_version: str = "default"
    prompt_version: str = "v1"
    semantic_version: str = "v1"
    graph_version: str = "v1"
    dataset_version: str = "1"
    evaluation_config_hash: str = "sha256:default"
    metric_registry_version: str = "v1"

    def to_dict(self) -> dict[str, str]:
        return {
            "system_version": self.system_version,
            "code_version": self.code_version,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "semantic_version": self.semantic_version,
            "graph_version": self.graph_version,
            "dataset_version": self.dataset_version,
            "evaluation_config_hash": self.evaluation_config_hash,
            "metric_registry_version": self.metric_registry_version,
        }


@dataclass
class MetricDefinition:
    """Configurable definition of an evaluation metric with direction and weighting."""

    metric_name: str
    category: str  # retrieval, rag, sql, semantic, graph, agent, orchestration, performance, cost
    direction: MetricDirection
    threshold: float
    weight: float
    version: str = "v1"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "category": self.category,
            "direction": self.direction.value,
            "threshold": self.threshold,
            "weight": self.weight,
            "version": self.version,
            "description": self.description,
        }


@dataclass
class Benchmark:
    """Versioned benchmark specification target."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    task_type: str
    target: EvaluationTarget
    dataset_id: uuid.UUID
    version: int = 1
    baseline_run_id: uuid.UUID | None = None
    status: str = "ACTIVE"
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "target": self.target.value,
            "dataset_id": str(self.dataset_id),
            "version": self.version,
            "baseline_run_id": str(self.baseline_run_id) if self.baseline_run_id else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class EvaluationSuite:
    """Unified multi-target evaluation suite collection."""

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: str | None
    benchmark_ids: list[str] = field(default_factory=list)
    version: int = 1
    status: str = "ACTIVE"
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "name": self.name,
            "description": self.description,
            "benchmark_ids": self.benchmark_ids,
            "version": self.version,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class QualityScore:
    """Composite, weighted quality score across evaluation dimensions."""

    retrieval_score: float = 0.0
    grounding_score: float = 0.0
    citation_score: float = 0.0
    semantic_score: float = 0.0
    sql_score: float = 0.0
    graph_score: float = 0.0
    agent_score: float = 0.0
    latency_score: float = 0.0
    cost_score: float = 0.0
    answer_quality_score: float = 0.0
    overall_score: float = 0.0
    weights: dict[str, float] = field(default_factory=dict)
    breakdown: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "retrieval_score": round(self.retrieval_score, 4),
            "grounding_score": round(self.grounding_score, 4),
            "citation_score": round(self.citation_score, 4),
            "semantic_score": round(self.semantic_score, 4),
            "sql_score": round(self.sql_score, 4),
            "graph_score": round(self.graph_score, 4),
            "agent_score": round(self.agent_score, 4),
            "latency_score": round(self.latency_score, 4),
            "cost_score": round(self.cost_score, 4),
            "answer_quality_score": round(self.answer_quality_score, 4),
            "overall_score": round(self.overall_score, 4),
            "weights": self.weights,
            "breakdown": self.breakdown,
        }


@dataclass
class CaseLevelDiff:
    """Granular comparison of an individual evaluation test case between baseline and candidate."""

    case_id: str
    query: str
    difficulty: DifficultyLevel
    baseline_status: str
    candidate_status: str
    reason: str
    metric_changes: dict[str, Any] = field(default_factory=dict)
    evidence_differences: dict[str, Any] = field(default_factory=dict)
    route_differences: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "query": self.query,
            "difficulty": self.difficulty.value,
            "baseline_status": self.baseline_status,
            "candidate_status": self.candidate_status,
            "reason": self.reason,
            "metric_changes": self.metric_changes,
            "evidence_differences": self.evidence_differences,
            "route_differences": self.route_differences,
        }


@dataclass
class RegressionFinding:
    """Detected metric regression with statistical significance and severity."""

    benchmark_id: uuid.UUID
    run_id: uuid.UUID
    baseline_run_id: uuid.UUID
    metric_name: str
    baseline_value: float
    current_value: float
    drop_percentage: float
    severity: RegressionSeverity
    details: dict[str, Any] = field(default_factory=dict)
    is_statistically_significant: bool = False
    p_value: float | None = None
    case_diffs: list[CaseLevelDiff] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": str(self.benchmark_id),
            "run_id": str(self.run_id),
            "baseline_run_id": str(self.baseline_run_id),
            "metric_name": self.metric_name,
            "baseline_value": round(self.baseline_value, 4),
            "current_value": round(self.current_value, 4),
            "drop_percentage": round(self.drop_percentage, 4),
            "severity": self.severity.value,
            "details": self.details,
            "is_statistically_significant": self.is_statistically_significant,
            "p_value": round(self.p_value, 4) if self.p_value is not None else None,
            "case_diffs_count": len(self.case_diffs),
        }


@dataclass
class QualityGateRule:
    """Individual rule for gating an evaluation metric."""

    metric_name: str
    min_threshold: float | None = None
    max_threshold: float | None = None
    max_drop_percentage: float | None = None
    is_critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "min_threshold": self.min_threshold,
            "max_threshold": self.max_threshold,
            "max_drop_percentage": self.max_drop_percentage,
            "is_critical": self.is_critical,
        }


@dataclass
class QualityGateResult:
    """Outcome of evaluating candidate metrics against a quality gate."""

    gate_id: uuid.UUID
    run_id: uuid.UUID
    decision: QualityGateDecision
    scorecard: dict[str, Any]
    violations: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": str(self.gate_id),
            "run_id": str(self.run_id),
            "decision": self.decision.value,
            "scorecard": self.scorecard,
            "violations": self.violations,
        }


@dataclass
class CalibrationBucket:
    """Bin for reliability diagram calculation."""

    bin_start: float
    bin_end: float
    avg_confidence: float
    accuracy: float
    sample_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "bin_start": round(self.bin_start, 2),
            "bin_end": round(self.bin_end, 2),
            "avg_confidence": round(self.avg_confidence, 4),
            "accuracy": round(self.accuracy, 4),
            "sample_count": self.sample_count,
        }


@dataclass
class CalibrationAnalysis:
    """Complete confidence calibration report including ECE and Brier score."""

    run_id: uuid.UUID
    ece: float
    brier_score: float
    buckets: list[CalibrationBucket] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "ece": round(self.ece, 4),
            "brier_score": round(self.brier_score, 4),
            "buckets": [b.to_dict() for b in self.buckets],
        }


@dataclass
class ProductionSample:
    """Production execution sample sanitized with PII filters and retention policy."""

    id: uuid.UUID
    organization_id: uuid.UUID
    query: str
    response: str
    sampling_strategy: SamplingStrategy
    data_sensitivity: str
    redacted: bool
    expires_at: datetime
    source_execution_id: str | None = None
    created_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "source_execution_id": self.source_execution_id,
            "query": self.query,
            "response": self.response,
            "sampling_strategy": self.sampling_strategy.value,
            "data_sensitivity": self.data_sensitivity,
            "redacted": self.redacted,
            "expires_at": self.expires_at.isoformat(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class HumanEvaluation:
    """Human expert evaluation assessment for a case or production sample."""

    id: uuid.UUID
    organization_id: uuid.UUID
    evaluator_id: uuid.UUID
    accuracy_score: float  # 1.0 to 5.0
    helpfulness_score: float  # 1.0 to 5.0
    grounding_score: float  # 1.0 to 5.0
    clarity_score: float  # 1.0 to 5.0
    sample_id: uuid.UUID | None = None
    case_result_id: uuid.UUID | None = None
    comments: str | None = None
    created_at: datetime | None = None
    evaluation_source: EvaluationSource = EvaluationSource.HUMAN

    def normalized_score(self) -> float:
        """Normalized overall score on [0.0, 1.0] scale."""
        raw_mean = (
            self.accuracy_score + self.helpfulness_score + self.grounding_score + self.clarity_score
        ) / 4.0
        return max(0.0, min(1.0, (raw_mean - 1.0) / 4.0))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "evaluator_id": str(self.evaluator_id),
            "sample_id": str(self.sample_id) if self.sample_id else None,
            "case_result_id": str(self.case_result_id) if self.case_result_id else None,
            "accuracy_score": self.accuracy_score,
            "helpfulness_score": self.helpfulness_score,
            "grounding_score": self.grounding_score,
            "clarity_score": self.clarity_score,
            "normalized_score": round(self.normalized_score(), 4),
            "comments": self.comments,
            "evaluation_source": self.evaluation_source.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class ComparisonReport:
    """Differential evaluation report between models, prompts, or semantic/graph versions."""

    comparison_type: str  # MODEL, PROMPT, SEMANTIC, GRAPH
    baseline_id: str
    candidate_id: str
    metrics_diff: dict[str, dict[str, float]] = field(default_factory=dict)
    winner: str | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_type": self.comparison_type,
            "baseline_id": self.baseline_id,
            "candidate_id": self.candidate_id,
            "metrics_diff": self.metrics_diff,
            "winner": self.winner,
            "summary": self.summary,
        }


@dataclass
class JudgeMonitoringReport:
    """Agreement and drift analysis between LLM judge and human evaluations."""

    total_samples: int
    agreement_rate: float
    drift_score: float
    disagreement_count: int
    mean_judge_score: float
    mean_human_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "agreement_rate": round(self.agreement_rate, 4),
            "drift_score": round(self.drift_score, 4),
            "disagreement_count": self.disagreement_count,
            "mean_judge_score": round(self.mean_judge_score, 4),
            "mean_human_score": round(self.mean_human_score, 4),
        }
