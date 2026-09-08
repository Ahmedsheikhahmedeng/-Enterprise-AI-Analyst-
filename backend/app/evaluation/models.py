"""Domain data models and metrics structures for Enterprise AI Evaluation."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID


class EvaluationCaseType(StrEnum):
    """Execution modality target for an evaluation case."""

    RAG = "rag"
    SQL = "sql"
    HYBRID = "hybrid"
    NONE = "none"


class CaseDifficulty(StrEnum):
    """Categorical complexity level of an evaluation case."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class RunStatus(StrEnum):
    """Execution status of an evaluation benchmark run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RetrievalMetrics:
    """Quantitative evaluation metrics for information retrieval rank lists."""

    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    precision_at_5: float = 0.0
    hit_rate_at_1: float = 0.0
    hit_rate_at_3: float = 0.0
    hit_rate_at_5: float = 0.0
    hit_rate_at_10: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "recall@1": self.recall_at_1,
            "recall@3": self.recall_at_3,
            "recall@5": self.recall_at_5,
            "recall@10": self.recall_at_10,
            "precision@5": self.precision_at_5,
            "hit_rate@1": self.hit_rate_at_1,
            "hit_rate@3": self.hit_rate_at_3,
            "hit_rate@5": self.hit_rate_at_5,
            "hit_rate@10": self.hit_rate_at_10,
            "mrr": self.mrr,
            "ndcg@5": self.ndcg_at_5,
        }


@dataclass
class RAGMetrics:
    """Metrics for context retrieval and qualitative answer generation."""

    context_recall: float = 0.0
    context_precision: float = 0.0
    answer_relevance: float = 0.0
    faithfulness: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "context_recall": self.context_recall,
            "context_precision": self.context_precision,
            "answer_relevance": self.answer_relevance,
            "faithfulness": self.faithfulness,
        }


@dataclass
class SQLMetrics:
    """Metrics evaluating SQL validity, safety, and numeric accuracy."""

    sql_validity: float = 0.0
    sql_safety: float = 1.0
    sql_semantic_correctness: float = 0.0
    result_correctness: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "sql_validity": self.sql_validity,
            "sql_safety": self.sql_safety,
            "sql_semantic_correctness": self.sql_semantic_correctness,
            "result_correctness": self.result_correctness,
        }


@dataclass
class CitationMetrics:
    """Metrics measuring grounding citation coverage, precision, and phantom rates."""

    citation_precision: float = 0.0
    citation_recall: float = 0.0
    citation_coverage: float = 0.0
    invalid_citation_rate: float = 0.0
    phantom_citation_rate: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "citation_precision": self.citation_precision,
            "citation_recall": self.citation_recall,
            "citation_coverage": self.citation_coverage,
            "invalid_citation_rate": self.invalid_citation_rate,
            "phantom_citation_rate": self.phantom_citation_rate,
        }


@dataclass
class GroundingMetrics:
    """Measurement of claim-to-evidence support levels."""

    groundedness_score: float = 0.0  # 1.0 (fully), 0.5 (partially), 0.0 (ungrounded)
    groundedness_label: str = "ungrounded"
    supported_claims_ratio: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "groundedness_score": self.groundedness_score,
            "groundedness_label": self.groundedness_label,
            "supported_claims_ratio": self.supported_claims_ratio,
        }


@dataclass
class HallucinationMetrics:
    """Identification and scoring of unsupported assertions."""

    hallucination_score: float = 1.0  # 1.0 means clean (0 hallucinations)
    unsupported_numeric_count: int = 0
    phantom_citation_count: int = 0
    unsupported_entity_count: int = 0
    unsupported_date_count: int = 0
    unsupported_percentage_count: int = 0

    @property
    def total_hallucinations(self) -> int:
        return (
            self.unsupported_numeric_count
            + self.phantom_citation_count
            + self.unsupported_entity_count
            + self.unsupported_date_count
            + self.unsupported_percentage_count
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "hallucination_score": self.hallucination_score,
            "unsupported_numeric_count": self.unsupported_numeric_count,
            "phantom_citation_count": self.phantom_citation_count,
            "unsupported_entity_count": self.unsupported_entity_count,
            "unsupported_date_count": self.unsupported_date_count,
            "unsupported_percentage_count": self.unsupported_percentage_count,
            "total_hallucinations": self.total_hallucinations,
        }


@dataclass
class LatencyMetrics:
    """Observability timings for benchmark execution phases."""

    planning_ms: float = 0.0
    sql_ms: float = 0.0
    rag_ms: float = 0.0
    generation_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "planning_ms": self.planning_ms,
            "sql_ms": self.sql_ms,
            "rag_ms": self.rag_ms,
            "generation_ms": self.generation_ms,
            "total_ms": self.total_ms,
        }


@dataclass
class CostMetrics:
    """Token consumption and financial cost estimations."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


@dataclass
class Scorecard:
    """Aggregated quality, performance, and cost summary across an entire benchmark run."""

    run_id: UUID
    dataset_id: UUID
    dataset_version: int
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float

    # Core QA Metrics
    route_accuracy: float
    retrieval_recall_at_5: float
    citation_precision: float
    groundedness: float
    sql_accuracy: float
    hybrid_accuracy: float
    hallucination_rate: float

    # Latency percentiles (ms)
    p50_latency_ms: float
    p75_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float

    # Cost
    cost_per_query_usd: float
    total_cost_usd: float

    # High-level segmented scores [0.0 - 1.0]
    quality_score: float
    performance_score: float
    cost_score: float
    overall_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": str(self.run_id),
            "dataset_id": str(self.dataset_id),
            "dataset_version": self.dataset_version,
            "total_cases": self.total_cases,
            "passed_cases": self.passed_cases,
            "failed_cases": self.failed_cases,
            "pass_rate": round(self.pass_rate, 4),
            "metrics": {
                "route_accuracy": round(self.route_accuracy, 4),
                "retrieval_recall@5": round(self.retrieval_recall_at_5, 4),
                "citation_precision": round(self.citation_precision, 4),
                "groundedness": round(self.groundedness, 4),
                "sql_accuracy": round(self.sql_accuracy, 4),
                "hybrid_accuracy": round(self.hybrid_accuracy, 4),
                "hallucination_rate": round(self.hallucination_rate, 4),
            },
            "latency": {
                "p50_ms": round(self.p50_latency_ms, 2),
                "p75_ms": round(self.p75_latency_ms, 2),
                "p90_ms": round(self.p90_latency_ms, 2),
                "p95_ms": round(self.p95_latency_ms, 2),
                "p99_ms": round(self.p99_latency_ms, 2),
            },
            "cost": {
                "cost_per_query_usd": round(self.cost_per_query_usd, 6),
                "total_cost_usd": round(self.total_cost_usd, 6),
            },
            "segmented_scores": {
                "quality_score": round(self.quality_score, 4),
                "performance_score": round(self.performance_score, 4),
                "cost_score": round(self.cost_score, 4),
                "overall_score": round(self.overall_score, 4),
            },
        }


@dataclass
class RegressionReport:
    """Detailed differential analysis comparing candidate benchmark run against baseline."""

    baseline_run_id: UUID
    candidate_run_id: UUID
    status: str  # "PASS", "WARNING", "FAIL"
    quality_delta: float
    retrieval_delta: float
    grounding_delta: float
    sql_delta: float
    latency_p95_delta_pct: float
    cost_delta_pct: float
    new_failures: list[str] = field(default_factory=list)
    regressions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_run_id": str(self.baseline_run_id),
            "candidate_run_id": str(self.candidate_run_id),
            "status": self.status,
            "deltas": {
                "quality_delta": round(self.quality_delta, 4),
                "retrieval_delta": round(self.retrieval_delta, 4),
                "grounding_delta": round(self.grounding_delta, 4),
                "sql_delta": round(self.sql_delta, 4),
                "latency_p95_delta_pct": round(self.latency_p95_delta_pct, 4),
                "cost_delta_pct": round(self.cost_delta_pct, 4),
            },
            "new_failures_count": len(self.new_failures),
            "new_failures": self.new_failures,
            "regressions": self.regressions,
        }
