"""Observability instrumentation, Prometheus metrics, and audit constants for Continuous Evaluation."""

import logging

from app.observability.metrics import MetricsRegistry, get_metrics_registry

logger = logging.getLogger(__name__)

# Structured Continuous Evaluation Audit Log Action Constants
AUDIT_EVALUATION_STARTED = "EVALUATION_STARTED"
AUDIT_EVALUATION_COMPLETED = "EVALUATION_COMPLETED"
AUDIT_REGRESSION_DETECTED = "REGRESSION_DETECTED"
AUDIT_QUALITY_GATE_FAILED = "QUALITY_GATE_FAILED"
AUDIT_QUALITY_GATE_PASSED = "QUALITY_GATE_PASSED"
AUDIT_RELEASE_BLOCKED = "RELEASE_BLOCKED"
AUDIT_MODEL_COMPARISON_COMPLETED = "MODEL_COMPARISON_COMPLETED"
AUDIT_HUMAN_EVALUATION_SUBMITTED = "HUMAN_EVALUATION_SUBMITTED"
AUDIT_CALIBRATION_UPDATED = "CALIBRATION_UPDATED"


class ContinuousEvaluationInstrumentation:
    """Instruments enterprise continuous evaluation, benchmarks, quality gates, and drift."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_run_started(self, evaluation_type: str, target: str, language: str = "en") -> None:
        """Record initiation of an evaluation run."""
        clean_type = (evaluation_type or "benchmark").lower()
        clean_target = (target or "end_to_end").lower()
        clean_lang = (language or "en").lower()

        self.metrics.increment(
            "evaluation_runs_total",
            value=1.0,
            labels={"evaluation_type": clean_type, "target": clean_target, "language": clean_lang},
            description="Total continuous evaluation runs started",
        )

    def record_run_completed(
        self,
        evaluation_type: str,
        target: str,
        status: str,
        duration_seconds: float,
        score: float,
        language: str = "en",
    ) -> None:
        """Record run completion and timing."""
        clean_type = (evaluation_type or "benchmark").lower()
        clean_target = (target or "end_to_end").lower()
        clean_status = (status or "completed").lower()
        clean_lang = (language or "en").lower()

        if clean_status in ("failed", "error"):
            self.metrics.increment(
                "evaluation_failures_total",
                value=1.0,
                labels={"evaluation_type": clean_type, "target": clean_target},
                description="Total failed evaluation runs",
            )

        if duration_seconds > 0.0:
            self.metrics.observe(
                "evaluation_duration_seconds",
                value=duration_seconds,
                labels={"evaluation_type": clean_type, "target": clean_target},
                description="Duration of evaluation runs in seconds",
            )

        self.metrics.gauge(
            "evaluation_score",
            value=score,
            labels={"evaluation_type": clean_type, "target": clean_target, "language": clean_lang},
            description="Latest evaluation composite quality score",
        )

    def record_regression_detected(self, target: str, severity: str) -> None:
        """Record a performance or accuracy regression finding."""
        clean_target = (target or "end_to_end").lower()
        clean_sev = (severity or "warning").lower()

        self.metrics.increment(
            "regressions_total",
            value=1.0,
            labels={"target": clean_target, "severity": clean_sev},
            description="Total detected regressions against baseline",
        )

    def record_quality_gate_result(self, decision: str, target: str) -> None:
        """Record outcome of quality gate check."""
        clean_dec = (decision or "pass").lower()
        clean_target = (target or "end_to_end").lower()

        if clean_dec in ("fail", "block_release"):
            self.metrics.increment(
                "quality_gate_failures_total",
                value=1.0,
                labels={"target": clean_target, "status": clean_dec},
                description="Total quality gate evaluation failures",
            )
        if clean_dec == "block_release":
            self.metrics.increment(
                "quality_gate_blocks_total",
                value=1.0,
                labels={"target": clean_target},
                description="Total production releases blocked by quality gates",
            )

    def record_calibration(self, target: str, ece: float) -> None:
        """Record confidence calibration error metric."""
        clean_target = (target or "end_to_end").lower()
        self.metrics.gauge(
            "calibration_error",
            value=ece,
            labels={"target": clean_target},
            description="Expected Calibration Error (ECE) for model confidence",
        )

    def record_judge_disagreement(self, model_family: str) -> None:
        """Record divergence between human evaluation and LLM judge."""
        clean_family = (model_family or "default").lower()
        self.metrics.increment(
            "judge_disagreement_total",
            value=1.0,
            labels={"model_family": clean_family},
            description="Total disagreements between LLM judge and human evaluation",
        )

    def record_production_quality(self, target: str, score: float, language: str = "en") -> None:
        """Record sampled production quality metric."""
        clean_target = (target or "end_to_end").lower()
        clean_lang = (language or "en").lower()
        self.metrics.gauge(
            "production_quality_score",
            value=score,
            labels={"target": clean_target, "language": clean_lang},
            description="Continuously monitored production quality score",
        )


_instance: ContinuousEvaluationInstrumentation | None = None


def get_continuous_evaluation_instrumentation() -> ContinuousEvaluationInstrumentation:
    """Singleton getter for continuous evaluation instrumentation."""
    global _instance
    if _instance is None:
        _instance = ContinuousEvaluationInstrumentation()
    return _instance
