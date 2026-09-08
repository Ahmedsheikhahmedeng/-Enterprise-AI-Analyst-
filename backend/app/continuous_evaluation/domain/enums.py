"""Domain enums for Enterprise Continuous AI Evaluation, Benchmarking & Quality Monitoring."""

from enum import StrEnum


class EvaluationTarget(StrEnum):
    """Architectural layer or subsystem targeted for evaluation."""

    RAG = "RAG"
    SQL = "SQL"
    SEMANTIC = "SEMANTIC"
    GRAPH = "GRAPH"
    AGENT = "AGENT"
    ORCHESTRATION = "ORCHESTRATION"
    LLM = "LLM"
    END_TO_END = "END_TO_END"


class DifficultyLevel(StrEnum):
    """Categorization of evaluation test case complexity."""

    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"
    EXPERT = "EXPERT"


class MetricDirection(StrEnum):
    """Directional preference for metric optimization and regression detection."""

    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"
    TARGET_RANGE = "TARGET_RANGE"


class RegressionSeverity(StrEnum):
    """Categorical severity rating of a performance drop against baseline."""

    INFO = "INFO"
    WARNING = "WARNING"
    MAJOR = "MAJOR"
    CRITICAL = "CRITICAL"


class QualityGateDecision(StrEnum):
    """Enforcement outcome of evaluating quality gates against benchmark scorecards."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    BLOCK_RELEASE = "BLOCK_RELEASE"


class EvaluationSource(StrEnum):
    """Origin methodology for evaluation scores."""

    AUTOMATED = "AUTOMATED"
    LLM_JUDGE = "LLM_JUDGE"
    HUMAN = "HUMAN"


class SamplingStrategy(StrEnum):
    """Production workload sampling strategy for continuous quality monitoring."""

    RANDOM = "RANDOM"
    RISK_BASED = "RISK_BASED"
    FAILURE_BASED = "FAILURE_BASED"
    LANGUAGE_BASED = "LANGUAGE_BASED"


class ReleaseStatus(StrEnum):
    """Status of release approval gating deployment."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
