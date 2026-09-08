"""Observability instrumentation and Prometheus metrics for Response Orchestration."""

import logging

from app.observability.metrics import MetricsRegistry, get_metrics_registry

logger = logging.getLogger(__name__)

# Structured Audit Log Action Constants
AUDIT_ORCHESTRATION_STARTED = "ORCHESTRATION_STARTED"
AUDIT_ORCHESTRATION_COMPLETED = "ORCHESTRATION_COMPLETED"
AUDIT_ORCHESTRATION_FAILED = "ORCHESTRATION_FAILED"
AUDIT_ORCHESTRATION_BLOCKED = "ORCHESTRATION_BLOCKED"
AUDIT_DECISION_CREATED = "DECISION_CREATED"
AUDIT_CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
AUDIT_EVIDENCE_CONFLICT_DETECTED = "EVIDENCE_CONFLICT_DETECTED"
AUDIT_RESPONSE_VERIFICATION_FAILED = "RESPONSE_VERIFICATION_FAILED"
AUDIT_RESPONSE_PUBLISHED = "RESPONSE_PUBLISHED"


class OrchestrationInstrumentation:
    """Instruments enterprise AI response orchestration lifecycle with low-cardinality metrics."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_request_started(self, mode: str, execution_strategy: str) -> None:
        """Record inception of an enterprise query execution."""
        clean_mode = (mode or "auto").lower()
        clean_strat = (execution_strategy or "none").lower()
        self.metrics.increment(
            "orchestration_requests_total",
            value=1.0,
            labels={"mode": clean_mode, "execution_strategy": clean_strat},
            description="Total canonical enterprise orchestration requests initiated",
        )

    def record_request_completed(
        self,
        mode: str,
        execution_strategy: str,
        status: str,
        decision: str,
        duration_sec: float,
        confidence: float,
        evidence_coverage: float,
    ) -> None:
        """Record completed orchestration outcome, latency, and calibrated scores."""
        clean_mode = (mode or "auto").lower()
        clean_strat = (execution_strategy or "none").lower()
        clean_status = (status or "completed").lower()
        clean_decision = (decision or "answer").lower()

        labels = {
            "mode": clean_mode,
            "status": clean_status,
            "decision": clean_decision,
            "execution_strategy": clean_strat,
        }

        # 1. Total finished requests
        if clean_status in ("completed", "success"):
            self.metrics.increment(
                "orchestration_success_total",
                value=1.0,
                labels=labels,
                description="Successfully completed canonical orchestration requests",
            )
        elif clean_status in ("partial", "needs_clarification", "insufficient_evidence"):
            self.metrics.increment(
                "orchestration_partial_total",
                value=1.0,
                labels=labels,
                description="Partially fulfilled or clarification-bound orchestration requests",
            )
        else:
            self.metrics.increment(
                "orchestration_failure_total",
                value=1.0,
                labels=labels,
                description="Failed or blocked canonical orchestration requests",
            )

        # 2. Execution duration
        self.metrics.observe(
            "orchestration_duration_seconds",
            value=max(duration_sec, 0.0),
            labels={"mode": clean_mode, "execution_strategy": clean_strat},
            description="End-to-end duration for enterprise response orchestration",
        )

        # 3. Confidence score distribution
        self.metrics.observe(
            "orchestration_confidence",
            value=max(0.0, min(confidence, 1.0)),
            labels={"decision": clean_decision},
            description="Calibrated confidence scores for generated enterprise decisions",
        )

        # 4. Evidence coverage distribution
        self.metrics.observe(
            "orchestration_evidence_coverage",
            value=max(0.0, min(evidence_coverage, 1.0)),
            labels={"decision": clean_decision},
            description="Evidence coverage ratio (supported claims / total claims)",
        )

    def record_conflict_detected(self, conflict_type: str, severity: str) -> None:
        """Record cross-source evidence conflict."""
        self.metrics.increment(
            "orchestration_conflict_total",
            value=1.0,
            labels={"conflict_type": conflict_type.lower(), "severity": severity.lower()},
            description="Total factual or numerical contradictions detected across evidence",
        )

    def record_clarification_requested(self, reason: str) -> None:
        """Record question clarification invocation."""
        self.metrics.increment(
            "orchestration_clarification_total",
            value=1.0,
            labels={"reason": reason.lower()},
            description="Total disambiguation clarification questions prompted to user",
        )

    def record_verification_failure(self, failure_type: str) -> None:
        """Record post-generation grounding or citation verification failure."""
        self.metrics.increment(
            "orchestration_verification_failure_total",
            value=1.0,
            labels={"failure_type": failure_type.lower()},
            description="Total response verification failures (phantom citations, unsupported claims)",
        )


_global_instrumentation: OrchestrationInstrumentation | None = None


def get_orchestration_instrumentation() -> OrchestrationInstrumentation:
    """Retrieve or create singleton OrchestrationInstrumentation."""
    global _global_instrumentation
    if _global_instrumentation is None:
        _global_instrumentation = OrchestrationInstrumentation()
    return _global_instrumentation
