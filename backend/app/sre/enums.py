"""Enumerations for SRE, Incident Lifecycle, Alerts, SLOs, and Operational Readiness."""

from enum import StrEnum


class MetricTypeEnum(StrEnum):
    """Categorical metric type measured by Service Level Indicators (SLIs)."""

    AVAILABILITY = "AVAILABILITY"
    ERROR_RATE = "ERROR_RATE"
    LATENCY_P50 = "LATENCY_P50"
    LATENCY_P95 = "LATENCY_P95"
    LATENCY_P99 = "LATENCY_P99"
    SATURATION_CPU = "SATURATION_CPU"
    SATURATION_MEMORY = "SATURATION_MEMORY"
    SATURATION_DB_POOL = "SATURATION_DB_POOL"
    QUEUE_LAG = "QUEUE_LAG"
    WORKER_HEALTH = "WORKER_HEALTH"
    DEPENDENCY_HEALTH = "DEPENDENCY_HEALTH"
    STREAM_HEALTH = "STREAM_HEALTH"


class SLOTypeEnum(StrEnum):
    """Target category for Service Level Objectives (SLOs)."""

    AVAILABILITY = "AVAILABILITY"
    LATENCY = "LATENCY"
    SUCCESS_RATE = "SUCCESS_RATE"
    SATURATION = "SATURATION"


class SLOStatusEnum(StrEnum):
    """Operational compliance status of an evaluated SLO."""

    HEALTHY = "HEALTHY"
    AT_RISK = "AT_RISK"
    BREACHED = "BREACHED"


class AlertSeverityEnum(StrEnum):
    """Urgency and operational impact classification of alerts."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertStatusEnum(StrEnum):
    """Lifecycle state of an operational alert."""

    FIRING = "FIRING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class IncidentSeverityEnum(StrEnum):
    """Enterprise incident classification scale."""

    SEV1 = "SEV1"  # Critical platform outage or widespread service collapse
    SEV2 = "SEV2"  # Major degradation of primary user-facing workflow
    SEV3 = "SEV3"  # Limited degradation or intermittent background failure
    SEV4 = "SEV4"  # Minor operational issue or non-impacting flaw


class IncidentStatusEnum(StrEnum):
    """Strict finite state machine stages for enterprise incidents."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    INVESTIGATING = "INVESTIGATING"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class DependencyHealthStatusEnum(StrEnum):
    """Health classification for internal and external backing dependencies."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


class MaintenanceStatusEnum(StrEnum):
    """Lifecycle status of scheduled maintenance windows."""

    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ReleaseGateDecisionEnum(StrEnum):
    """Automated SRE safety gate decision for production deployments."""

    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"


class OperationalStatusEnum(StrEnum):
    """Unified top-level health status of the enterprise platform."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"
    MAINTENANCE = "MAINTENANCE"
