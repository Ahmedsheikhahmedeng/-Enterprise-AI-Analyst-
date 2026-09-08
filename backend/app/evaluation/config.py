"""Configuration settings for Enterprise AI Evaluation & Quality Framework."""

from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation framework operational constraints, metric weights, and regression thresholds."""

    # Execution limits
    default_max_cases_per_run: int = 100
    case_timeout_seconds: float = 30.0
    run_total_timeout_seconds: float = 300.0

    # Numeric evaluation tolerances
    exact_numeric_tolerance: float = 0.0
    loose_numeric_tolerance_ratio: float = 0.05  # 5% relative tolerance
    strict_numeric_tolerance_ratio: float = 0.01  # 1% relative tolerance

    # Regression detection thresholds (percentage points)
    min_quality_score: float = 0.70
    max_allowed_quality_regression: float = 0.05  # 5% max quality drop
    max_allowed_retrieval_regression: float = 0.05  # 5% drop in Recall@5
    max_allowed_grounding_regression: float = 0.03  # 3% drop in Groundedness
    max_allowed_latency_increase_ratio: float = 0.20  # 20% max latency increase
    max_allowed_cost_increase_ratio: float = 0.25  # 25% max cost increase

    # Scorecard category weights (must sum to 1.0)
    scorecard_weights: dict[str, float] = field(
        default_factory=lambda: {
            "retrieval": 0.20,
            "sql": 0.20,
            "grounding": 0.20,
            "citation": 0.15,
            "answer": 0.15,
            "hallucination": 0.10,
        }
    )


@lru_cache(maxsize=1)
def get_evaluation_config() -> EvaluationConfig:
    """Singleton getter for EvaluationConfig."""
    return EvaluationConfig()
