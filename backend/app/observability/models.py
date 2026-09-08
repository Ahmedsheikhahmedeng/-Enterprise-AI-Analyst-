"""Domain data models and telemetry structures for Enterprise Observability."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class SpanStatus(StrEnum):
    """Execution status code for a distributed trace span."""

    OK = "OK"
    ERROR = "ERROR"
    UNSET = "UNSET"


class SpanKind(StrEnum):
    """Categorical kind of an execution span."""

    SERVER = "SERVER"
    CLIENT = "CLIENT"
    INTERNAL = "INTERNAL"


@dataclass
class SpanRecord:
    """Individual execution unit in a distributed trace hierarchy."""

    span_id: str
    trace_id: str
    parent_span_id: str | None
    name: str
    kind: SpanKind = SpanKind.INTERNAL
    start_time: float = 0.0
    end_time: float | None = None
    duration_ms: float = 0.0
    status: SpanStatus = SpanStatus.OK
    attributes: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": str(self.kind),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "status": str(self.status),
            "attributes": self.attributes,
            "error_message": self.error_message,
        }


@dataclass
class TelemetryEvent:
    """Discrete operational event (e.g. slow_request, dependency_failure)."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    trace_id: str = ""
    span_id: str | None = None
    request_id: str | None = None
    organization_id: str | None = None
    event_name: str = "custom_event"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    severity: str = "INFO"  # INFO, WARNING, ERROR, CRITICAL
    duration_ms: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "request_id": self.request_id,
            "organization_id": self.organization_id,
            "event_name": self.event_name,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "duration_ms": self.duration_ms,
            "attributes": self.attributes,
        }


@dataclass
class SLODefinition:
    """Service Level Objective target threshold and target configuration."""

    name: str
    description: str
    target: float  # e.g. 0.995 for 99.5% availability or 1500.0 for latency
    metric_name: str
    comparison: str = ">="  # ">=" or "<="


@dataclass
class ErrorBudget:
    """Calculated error budget status derived from observed metrics."""

    target: float
    observed: float
    budget_remaining: float  # normalized 0.0 - 1.0 (or negative if depleted)
    status: str  # "MET", "WARNING", "BREACHED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "observed": round(self.observed, 4),
            "budget_remaining": round(self.budget_remaining, 4),
            "status": self.status,
        }


@dataclass
class SLOResult:
    """Evaluation result for a specific Service Level Objective."""

    name: str
    description: str
    target: float
    observed: float
    status: str
    error_budget_remaining: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "target": self.target,
            "observed": round(self.observed, 4),
            "status": self.status,
            "error_budget_remaining": round(self.error_budget_remaining, 4),
        }


@dataclass
class AlertCondition:
    """Pre-configured operational health alert condition definition."""

    name: str
    condition_type: str  # "error_rate", "latency", "dependency", "slo"
    threshold: float
    severity: str  # "WARNING", "CRITICAL"
    description: str


@dataclass
class ActiveAlert:
    """Triggered operational alert state."""

    alert_id: str
    condition_name: str
    severity: str
    observed_value: float
    threshold: float
    message: str
    triggered_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "condition_name": self.condition_name,
            "severity": self.severity,
            "observed_value": round(self.observed_value, 4),
            "threshold": self.threshold,
            "message": self.message,
            "triggered_at": self.triggered_at.isoformat(),
        }


@dataclass
class ObservabilitySummary:
    """Consolidated operational snapshot of platform health, throughput, and costs."""

    requests_total: int
    success_rate: float
    error_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    active_requests: int
    analyst_requests: int
    sql_requests: int
    rag_requests: int
    llm_requests: int
    total_tokens: int
    total_cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests_total": self.requests_total,
            "success_rate": round(self.success_rate, 4),
            "error_rate": round(self.error_rate, 4),
            "latency": {
                "p50_ms": round(self.p50_latency_ms, 2),
                "p95_ms": round(self.p95_latency_ms, 2),
                "p99_ms": round(self.p99_latency_ms, 2),
            },
            "active_requests": self.active_requests,
            "modality_breakdown": {
                "analyst_requests": self.analyst_requests,
                "sql_requests": self.sql_requests,
                "rag_requests": self.rag_requests,
                "llm_requests": self.llm_requests,
            },
            "consumption": {
                "total_tokens": self.total_tokens,
                "total_cost_usd": round(self.total_cost_usd, 6),
            },
        }
