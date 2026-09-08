"""Pydantic schemas for Observability REST endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class ObservabilitySummaryResponse(BaseModel):
    """Aggregated operational metrics summary for the enterprise AI platform."""

    requests_total: int = Field(default=0, description="Total HTTP requests recorded")
    success_rate: float = Field(default=1.0, description="Observed success rate (0.0 - 1.0)")
    error_rate: float = Field(default=0.0, description="Observed error rate (0.0 - 1.0)")
    p50_ms: float = Field(default=0.0, description="Median latency in milliseconds")
    p95_ms: float = Field(default=0.0, description="95th percentile latency in milliseconds")
    p99_ms: float = Field(default=0.0, description="99th percentile latency in milliseconds")
    active_requests: int = Field(default=0, description="Current in-flight requests")
    analyst_requests: int = Field(default=0, description="Total AI analyst requests")
    sql_requests: int = Field(default=0, description="Total SQL agent queries")
    rag_requests: int = Field(default=0, description="Total RAG retrieval executions")
    llm_requests: int = Field(default=0, description="Total LLM provider calls")
    total_tokens: int = Field(default=0, description="Total tokens consumed across all providers")
    total_cost_usd: float = Field(default=0.0, description="Total expenditure in USD")


class DependencyStatus(BaseModel):
    """Granular health status of a single backing dependency."""

    status: str
    latency_ms: float
    last_success: str | None = None


class DependencyHealthResponse(BaseModel):
    """Overall dependency health status."""

    status: str
    timestamp: str
    dependencies: dict[str, DependencyStatus]


class SLOResponseItem(BaseModel):
    """Single SLO compliance evaluation result."""

    name: str
    target: float
    observed: float
    status: str
    error_budget_remaining: float


class SLOSummaryResponse(BaseModel):
    """Collection of SLO targets and error budget statuses."""

    overall_status: str
    slos: list[SLOResponseItem]


class AlertResponseItem(BaseModel):
    """Operational alert condition evaluation."""

    name: str
    severity: str
    message: str
    observed_value: float
    threshold: float
    is_active: bool


class AlertsResponse(BaseModel):
    """Active operational alerts summary."""

    total_active: int
    alerts: list[AlertResponseItem]


class TraceSpanResponseItem(BaseModel):
    """Single trace span representation."""

    span_id: str
    trace_id: str
    parent_span_id: str | None = None
    name: str
    kind: str
    duration_ms: float
    status: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceDetailResponse(BaseModel):
    """Detailed spans for a distributed trace."""

    trace_id: str
    spans: list[TraceSpanResponseItem]
