"""Domain exception hierarchy for Enterprise Continuous AI Evaluation."""


class ContinuousEvaluationError(Exception):
    """Base exception for all continuous evaluation workflows."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BenchmarkNotFoundError(ContinuousEvaluationError):
    """Raised when a specified benchmark cannot be found within tenant scope."""


class EvaluationSuiteNotFoundError(ContinuousEvaluationError):
    """Raised when an evaluation suite cannot be located."""


class QualityGateNotFoundError(ContinuousEvaluationError):
    """Raised when a quality gate configuration is missing."""


class QualityGateFailedError(ContinuousEvaluationError):
    """Raised when an evaluation run breaches non-negotiable quality gate thresholds."""


class ReleaseBlockedError(ContinuousEvaluationError):
    """Raised when deployment or release is prohibited due to quality gate failure."""


class RegressionThresholdExceededError(ContinuousEvaluationError):
    """Raised when a major or critical metric regression is detected against baseline."""


class InsufficientSampleError(ContinuousEvaluationError):
    """Raised when sample size is inadequate for statistically significant analysis."""


class PrivacyFilterViolationError(ContinuousEvaluationError):
    """Raised when production evaluation samples contain unsanitized sensitive PII or credentials."""
