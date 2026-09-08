"""Security Audit Event Logging & Telemetry Integration — TASK 22.

Provides centralized auditing for security-relevant occurrences:
- Records structured security audit logs without leaking secrets or raw attack payloads.
- Emits low-cardinality telemetry metrics for operational alerting and SLO tracking.
- Optionally persists to the immutable AuditLog database entity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.observability.metrics import MetricType, get_metrics_registry

logger = get_logger("security.audit")

# Supported Security Audit Event Types
EVENT_LOGIN_FAILED = "security.login_failed"
EVENT_JWT_REJECTED = "security.jwt_rejected"
EVENT_AUTHZ_DENIED = "security.authorization_denied"
EVENT_TENANT_VIOLATION = "security.tenant_violation"
EVENT_PROMPT_INJECTION = "security.prompt_injection_detected"
EVENT_SSRF_BLOCKED = "security.ssrf_blocked"
EVENT_FILE_REJECTED = "security.file_rejected"
EVENT_RATE_LIMITED = "security.rate_limited"
EVENT_REPLAY_REJECTED = "security.replay_rejected"

# Specific counter mapping
METRIC_SPECIFIC_MAP = {
    EVENT_AUTHZ_DENIED: "authorization_denied_total",
    EVENT_TENANT_VIOLATION: "tenant_violation_total",
    EVENT_PROMPT_INJECTION: "prompt_injection_detected_total",
    EVENT_SSRF_BLOCKED: "ssrf_blocked_total",
    EVENT_FILE_REJECTED: "file_upload_rejected_total",
    EVENT_RATE_LIMITED: "rate_limit_exceeded_total",
    EVENT_REPLAY_REJECTED: "replay_rejected_total",
}


@dataclass(frozen=True)
class SecurityAuditEvent:
    event_type: str
    severity: str  # "INFO", "WARNING", "HIGH", "CRITICAL"
    endpoint: str
    request_id: str | None = None
    trace_id: str | None = None
    user_id: str | None = None
    organization_id: str | None = None
    resource_type: str = "security"
    resource_id: str | None = None
    details: dict[str, Any] | None = None


class SecurityAuditor:
    """Auditor service recording security events across logging, metrics, and database."""

    @staticmethod
    def _register_metrics_if_needed() -> None:
        reg = get_metrics_registry()
        reg.register_metric(
            "security_events_total",
            MetricType.COUNTER,
            "Total count of security audit events observed",
        )
        for metric_name in METRIC_SPECIFIC_MAP.values():
            reg.register_metric(
                metric_name,
                MetricType.COUNTER,
                f"Total count of {metric_name.replace('_', ' ')}",
            )

    @classmethod
    async def record_event(
        cls,
        event: SecurityAuditEvent,
        db_session: AsyncSession | None = None,
    ) -> None:
        """Record a security audit event to structured logs, metrics, and DB."""
        # 1. Increment low-cardinality metrics
        cls._register_metrics_if_needed()
        reg = get_metrics_registry()
        clean_endpoint = event.endpoint.split("?")[0][:64] or "unknown"
        clean_severity = event.severity.upper()

        metric_labels = {
            "event_type": event.event_type,
            "severity": clean_severity,
            "endpoint": clean_endpoint,
        }

        reg.increment("security_events_total", 1.0, metric_labels)

        specific_metric = METRIC_SPECIFIC_MAP.get(event.event_type)
        if specific_metric:
            reg.increment(specific_metric, 1.0, {"endpoint": clean_endpoint})

        # 2. Structured log entry (scrubbed, no raw secrets or massive payloads)
        log_payload = {
            "security_event": event.event_type,
            "severity": clean_severity,
            "endpoint": clean_endpoint,
            "request_id": event.request_id,
            "trace_id": event.trace_id,
            "user_id": event.user_id,
            "organization_id": event.organization_id,
            "resource_id": event.resource_id,
            "details": event.details or {},
        }

        if clean_severity in ("HIGH", "CRITICAL"):
            logger.error("SECURITY ALERT: %s", log_payload)
        elif clean_severity == "WARNING":
            logger.warning("SECURITY WARNING: %s", log_payload)
        else:
            logger.info("SECURITY AUDIT: %s", log_payload)

        # 3. Persist to database AuditLog if an active session is provided
        if db_session is not None and event.organization_id:
            try:
                org_uuid = (
                    UUID(event.organization_id)
                    if isinstance(event.organization_id, str)
                    else event.organization_id
                )
                user_uuid = (
                    UUID(event.user_id)
                    if event.user_id and isinstance(event.user_id, str)
                    else None
                )

                audit_entry = AuditLog(
                    organization_id=org_uuid,
                    user_id=user_uuid,
                    action=event.event_type,
                    resource_type=event.resource_type,
                    resource_id=str(event.resource_id) if event.resource_id else None,
                    metadata_={
                        "severity": clean_severity,
                        "endpoint": clean_endpoint,
                        "request_id": event.request_id,
                        "trace_id": event.trace_id,
                        "details": event.details or {},
                    },
                )
                db_session.add(audit_entry)
                # Session flush can be performed by caller or transaction boundary
            except Exception as exc:
                logger.warning(
                    "Failed to persist security event to database AuditLog: %s", str(exc)
                )
