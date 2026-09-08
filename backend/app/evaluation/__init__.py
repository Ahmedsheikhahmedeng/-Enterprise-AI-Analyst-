"""Enterprise AI Evaluation & Quality Framework."""

from app.evaluation.benchmark import BenchmarkRunner
from app.evaluation.cases import CaseManager
from app.evaluation.config import EvaluationConfig, get_evaluation_config
from app.evaluation.dataset import DatasetManager
from app.evaluation.exceptions import (
    EvaluationAuthorizationError,
    EvaluationCaseNotFoundError,
    EvaluationDatasetNotFoundError,
    EvaluationError,
    EvaluationExecutionError,
    EvaluationRunNotFoundError,
    EvaluationValidationError,
    RegressionThresholdExceededError,
)
from app.evaluation.models import (
    CitationMetrics,
    CostMetrics,
    GroundingMetrics,
    HallucinationMetrics,
    LatencyMetrics,
    RAGMetrics,
    RegressionReport,
    RetrievalMetrics,
    Scorecard,
    SQLMetrics,
)
from app.evaluation.regression import RegressionDetector
from app.evaluation.scorecard import ScorecardGenerator
from app.evaluation.service import EvaluationService

__all__ = [
    "BenchmarkRunner",
    "CaseManager",
    "CitationMetrics",
    "CostMetrics",
    "DatasetManager",
    "EvaluationAuthorizationError",
    "EvaluationCaseNotFoundError",
    "EvaluationConfig",
    "EvaluationDatasetNotFoundError",
    "EvaluationError",
    "EvaluationExecutionError",
    "EvaluationRunNotFoundError",
    "EvaluationService",
    "EvaluationValidationError",
    "GroundingMetrics",
    "HallucinationMetrics",
    "LatencyMetrics",
    "RAGMetrics",
    "RegressionDetector",
    "RegressionReport",
    "RegressionThresholdExceededError",
    "RetrievalMetrics",
    "SQLMetrics",
    "Scorecard",
    "ScorecardGenerator",
    "get_evaluation_config",
]
