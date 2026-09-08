"""Domain Enums for Enterprise Reliability, Chaos Engineering & Production Readiness."""

from enum import StrEnum


class ScenarioCategory(StrEnum):
    """Categorization of reliability and chaos scenarios."""

    DEPENDENCY = "DEPENDENCY"
    NETWORK = "NETWORK"
    DATABASE = "DATABASE"
    QUEUE = "QUEUE"
    WORKER = "WORKER"
    LLM = "LLM"
    STREAMING = "STREAMING"
    RESOURCE = "RESOURCE"
    RECOVERY = "RECOVERY"
    SECURITY = "SECURITY"


class FaultType(StrEnum):
    """Specific deterministic fault injection types."""

    POSTGRES_UNAVAILABLE = "POSTGRES_UNAVAILABLE"
    POSTGRES_LATENCY = "POSTGRES_LATENCY"
    REDIS_UNAVAILABLE = "REDIS_UNAVAILABLE"
    REDIS_LATENCY = "REDIS_LATENCY"
    QDRANT_UNAVAILABLE = "QDRANT_UNAVAILABLE"
    QDRANT_LATENCY = "QDRANT_LATENCY"
    LLM_TIMEOUT = "LLM_TIMEOUT"
    LLM_5XX = "LLM_5XX"
    LLM_429 = "LLM_429"
    LLM_MALFORMED = "LLM_MALFORMED"
    LLM_FAILOVER = "LLM_FAILOVER"
    WORKER_CRASH = "WORKER_CRASH"
    QUEUE_BACKLOG = "QUEUE_BACKLOG"
    DLQ_TRANSITION = "DLQ_TRANSITION"
    SSE_DISCONNECT = "SSE_DISCONNECT"
    SSE_LATENCY = "SSE_LATENCY"
    API_LATENCY = "API_LATENCY"
    API_ERROR_SPIKE = "API_ERROR_SPIKE"


class InjectorLifecycle(StrEnum):
    """Lifecycle states of a fault injector."""

    IDLE = "IDLE"
    INJECTING = "INJECTING"
    ACTIVE = "ACTIVE"
    RECOVERING = "RECOVERING"
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"


class ReliabilityRunStatus(StrEnum):
    """Execution status of a reliability scenario run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    SKIPPED = "SKIPPED"


class FailureClassification(StrEnum):
    """Classification of observed failures during chaos evaluation."""

    DETECTED_AND_RECOVERED = "DETECTED_AND_RECOVERED"
    DETECTED_NOT_RECOVERED = "DETECTED_NOT_RECOVERED"
    NOT_DETECTED = "NOT_DETECTED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    DATA_INTEGRITY_FAILURE = "DATA_INTEGRITY_FAILURE"
    SECURITY_FAILURE = "SECURITY_FAILURE"
    ISOLATION_FAILURE = "ISOLATION_FAILURE"


class ReadinessDecision(StrEnum):
    """High-level production deployment readiness verdicts."""

    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    NOT_READY = "NOT_READY"


class AssertionType(StrEnum):
    """Types of invariants verified during and after chaos scenarios."""

    DATA_INTEGRITY = "DATA_INTEGRITY"
    TENANT_ISOLATION = "TENANT_ISOLATION"
    SECURITY_PRESERVED = "SECURITY_PRESERVED"
    NO_LEAKED_TASKS = "NO_LEAKED_TASKS"
    RETRY_STORM_PROTECTION = "RETRY_STORM_PROTECTION"
    CIRCUIT_BREAKER_ACTIVE = "CIRCUIT_BREAKER_ACTIVE"
    TIMEOUT_BUDGET_HONORED = "TIMEOUT_BUDGET_HONORED"
    GRACEFUL_DEGRADATION = "GRACEFUL_DEGRADATION"
    RECOVERY_SUCCESS = "RECOVERY_SUCCESS"


class AssertionStatus(StrEnum):
    """Status of an assertion verification check."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
