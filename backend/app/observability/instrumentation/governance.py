"""Observability instrumentation, audit event constants, and metrics for Enterprise Governance."""

import logging

from app.observability.metrics import MetricsRegistry, get_metrics_registry

logger = logging.getLogger(__name__)

# Structured Governance Audit Log Action Constants
AUDIT_APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
AUDIT_APPROVAL_STARTED = "APPROVAL_STARTED"
AUDIT_APPROVAL_APPROVED = "APPROVAL_APPROVED"
AUDIT_APPROVAL_REJECTED = "APPROVAL_REJECTED"
AUDIT_APPROVAL_CHANGES_REQUESTED = "APPROVAL_CHANGES_REQUESTED"
AUDIT_APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
AUDIT_APPROVAL_CANCELLED = "APPROVAL_CANCELLED"
AUDIT_APPROVAL_REVOKED = "APPROVAL_REVOKED"
AUDIT_GOVERNANCE_POLICY_CHANGED = "GOVERNANCE_POLICY_CHANGED"
AUDIT_RISK_ASSESSED = "RISK_ASSESSED"
AUDIT_ACTION_BLOCKED_BY_GOVERNANCE = "ACTION_BLOCKED_BY_GOVERNANCE"


class GovernanceInstrumentation:
    """Instruments enterprise governance, human-in-the-loop approvals, and risk checks."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_request_created(self, request_type: str, risk_level: str, status: str) -> None:
        """Record registration of a governed operation approval request."""
        clean_type = (request_type or "unknown").lower()
        clean_risk = (risk_level or "low").lower()
        clean_status = (status or "pending").lower()

        self.metrics.increment(
            "governance_requests_total",
            value=1.0,
            labels={"request_type": clean_type, "risk_level": clean_risk, "status": clean_status},
            description="Total governance approval requests created",
        )
        if clean_risk in ("high", "critical"):
            self.metrics.increment(
                "governance_high_risk_requests_total",
                value=1.0,
                labels={"request_type": clean_type, "risk_level": clean_risk},
                description="Total high-risk or critical approval requests requiring multi-approver or admin review",
            )

    def record_risk_assessed(self, request_type: str, risk_level: str) -> None:
        """Record risk assessment invocation."""
        clean_type = (request_type or "unknown").lower()
        clean_risk = (risk_level or "low").lower()
        self.metrics.increment(
            "governance_risk_assessment_total",
            value=1.0,
            labels={"request_type": clean_type, "risk_level": clean_risk},
            description="Total deterministic risk assessments executed",
        )

    def record_approval_granted(
        self, request_type: str, risk_level: str, decision: str, latency_seconds: float = 0.0
    ) -> None:
        """Record approval quorum achievement and grant."""
        clean_type = (request_type or "unknown").lower()
        clean_risk = (risk_level or "low").lower()
        clean_decision = (decision or "approved").lower()

        self.metrics.increment(
            "governance_approvals_total",
            value=1.0,
            labels={
                "request_type": clean_type,
                "risk_level": clean_risk,
                "decision": clean_decision,
            },
            description="Total approved governance requests",
        )
        if latency_seconds > 0.0:
            self.metrics.observe(
                "governance_approval_latency_seconds",
                value=latency_seconds,
                labels={"request_type": clean_type, "decision": clean_decision},
                description="Latency from request creation to final resolution in seconds",
            )

    def record_approval_rejected(self, request_type: str, risk_level: str, decision: str) -> None:
        """Record rejection or changes-requested decision."""
        clean_type = (request_type or "unknown").lower()
        clean_risk = (risk_level or "low").lower()
        clean_decision = (decision or "rejected").lower()

        self.metrics.increment(
            "governance_rejections_total",
            value=1.0,
            labels={
                "request_type": clean_type,
                "risk_level": clean_risk,
                "decision": clean_decision,
            },
            description="Total rejected or declined governance requests",
        )

    def record_approval_expired(self, request_type: str, risk_level: str) -> None:
        """Record approval window expiration."""
        clean_type = (request_type or "unknown").lower()
        clean_risk = (risk_level or "low").lower()

        self.metrics.increment(
            "governance_expirations_total",
            value=1.0,
            labels={"request_type": clean_type, "risk_level": clean_risk},
            description="Total approval requests that timed out and expired",
        )

    def record_action_blocked(self, request_type: str, risk_level: str) -> None:
        """Record operation blocked at pre-execution gate due to missing/invalid approval."""
        clean_type = (request_type or "unknown").lower()
        clean_risk = (risk_level or "low").lower()

        self.metrics.increment(
            "governance_blocked_actions_total",
            value=1.0,
            labels={"request_type": clean_type, "risk_level": clean_risk},
            description="Total actions blocked by governance pre-execution gates",
        )


_instance: GovernanceInstrumentation | None = None


def get_governance_instrumentation() -> GovernanceInstrumentation:
    """Singleton getter for governance instrumentation."""
    global _instance
    if _instance is None:
        _instance = GovernanceInstrumentation()
    return _instance
