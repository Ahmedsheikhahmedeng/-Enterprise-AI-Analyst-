"""Central ObservabilityService coordinating metrics summaries, health, SLOs, and traces."""

from typing import Any
from uuid import UUID

from app.observability.events import EventManager, get_event_manager
from app.observability.exceptions import ObservabilityAuthorizationError
from app.observability.exporters.prometheus import PrometheusExporter
from app.observability.health import DependencyHealthChecker, get_health_checker
from app.observability.metrics import MetricsRegistry, get_metrics_registry
from app.observability.schemas import (
    AlertResponseItem,
    AlertsResponse,
    DependencyHealthResponse,
    DependencyStatus,
    ObservabilitySummaryResponse,
    SLOResponseItem,
    SLOSummaryResponse,
    TraceDetailResponse,
    TraceSpanResponseItem,
)
from app.observability.slo import SLOEvaluator
from app.observability.tracing import TraceManager, get_trace_manager


def _calculate_histogram_percentile(hist_dict: dict[str, Any], percentile: float) -> float:
    """Approximate percentile from histogram cumulative bucket counts."""
    count = hist_dict.get("count", 0)
    if count == 0:
        return 0.0
    target_count = count * percentile
    buckets = hist_dict.get("buckets", [])
    for upper_bound, cumulative_count in buckets:
        if cumulative_count >= target_count:
            return float(upper_bound)
    # If beyond max bucket, return sum / count or last bucket
    return float(buckets[-1][0]) if buckets else 0.0


class ObservabilityService:
    """Service layer aggregating telemetry metrics, tracing, SLOs, alerts, and system health."""

    def __init__(
        self,
        metrics: MetricsRegistry | None = None,
        trace_manager: TraceManager | None = None,
        event_manager: EventManager | None = None,
        health_checker: DependencyHealthChecker | None = None,
        slo_evaluator: SLOEvaluator | None = None,
    ) -> None:
        self.metrics = metrics or get_metrics_registry()
        self.trace_manager = trace_manager or get_trace_manager()
        self.event_manager = event_manager or get_event_manager()
        self.health_checker = health_checker or get_health_checker()
        self.slo_evaluator = slo_evaluator or SLOEvaluator(self.metrics)
        self.prometheus_exporter = PrometheusExporter(self.metrics)

    def get_summary(self) -> ObservabilitySummaryResponse:
        """Produce an aggregated operational telemetry summary across platform components."""
        data = self.metrics.get_all_metrics()
        counters = data["counters"]
        histograms = data["histograms"]

        # HTTP Requests
        http_total = int(sum(item["value"] for item in counters.get("http_requests_total", [])))
        if http_total == 0:
            http_total = int(
                sum(item["value"] for item in counters.get("enterprise_ai_http_requests_total", []))
            )

        http_errors = int(sum(item["value"] for item in counters.get("http_errors_total", [])))
        if http_errors == 0:
            http_errors = int(
                sum(item["value"] for item in counters.get("enterprise_ai_http_errors_total", []))
            )

        error_rate = (http_errors / http_total) if http_total > 0 else 0.0
        success_rate = max(0.0, 1.0 - error_rate)

        # Percentiles
        p50 = 0.0
        p95 = 0.0
        p99 = 0.0
        http_hist = histograms.get("http_request_duration_ms", [])
        if http_hist:
            primary_hist = http_hist[0]
            p50 = _calculate_histogram_percentile(primary_hist, 0.50)
            p95 = _calculate_histogram_percentile(primary_hist, 0.95)
            p99 = _calculate_histogram_percentile(primary_hist, 0.99)

        # In flight
        active_requests = int(
            sum(item["value"] for item in counters.get("http_requests_in_flight", []))
        )
        active_requests = max(0, active_requests)

        # Component counts
        analyst_reqs = int(
            sum(item["value"] for item in counters.get("analyst_requests_total", []))
        )
        if analyst_reqs == 0:
            analyst_reqs = int(
                sum(
                    item["value"]
                    for item in counters.get("enterprise_ai_analyst_requests_total", [])
                )
            )

        sql_reqs = int(sum(item["value"] for item in counters.get("sql_queries_total", [])))
        if sql_reqs == 0:
            sql_reqs = int(
                sum(item["value"] for item in counters.get("enterprise_ai_sql_queries_total", []))
            )

        rag_reqs = int(sum(item["value"] for item in counters.get("rag_requests_total", [])))
        if rag_reqs == 0:
            rag_reqs = int(
                sum(item["value"] for item in counters.get("enterprise_ai_rag_requests_total", []))
            )

        llm_reqs = int(sum(item["value"] for item in counters.get("llm_requests_total", [])))
        if llm_reqs == 0:
            llm_reqs = int(
                sum(item["value"] for item in counters.get("enterprise_ai_llm_requests_total", []))
            )

        total_tokens = int(sum(item["value"] for item in counters.get("llm_total_tokens", [])))
        if total_tokens == 0:
            total_tokens = int(
                sum(item["value"] for item in counters.get("enterprise_ai_llm_tokens_total", []))
            )

        total_cost = float(sum(item["value"] for item in counters.get("ai_cost_total", [])))
        if total_cost == 0.0:
            total_cost = float(sum(item["value"] for item in counters.get("llm_cost_total", [])))

        return ObservabilitySummaryResponse(
            requests_total=http_total,
            success_rate=round(success_rate, 4),
            error_rate=round(error_rate, 4),
            p50_ms=round(p50, 2),
            p95_ms=round(p95, 2),
            p99_ms=round(p99, 2),
            active_requests=active_requests,
            analyst_requests=analyst_reqs,
            sql_requests=sql_reqs,
            rag_requests=rag_reqs,
            llm_requests=llm_reqs,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 6),
        )

    def export_prometheus_metrics(self) -> str:
        """Export all registered metrics formatted in Prometheus exposition format."""
        return str(self.prometheus_exporter.export())

    async def get_dependency_health(
        self,
        db_engine: Any = None,
        redis_client: Any = None,
        qdrant_client: Any = None,
        llm_provider_ok: bool = True,
    ) -> DependencyHealthResponse:
        """Probe all infrastructure backing dependencies."""
        raw_health = await self.health_checker.check_dependencies(
            db_engine=db_engine,
            redis_client=redis_client,
            qdrant_client=qdrant_client,
            llm_provider_ok=llm_provider_ok,
        )
        dep_dict = {}
        for name, info in raw_health.get("dependencies", {}).items():
            dep_dict[name] = DependencyStatus(
                status=info["status"],
                latency_ms=info["latency_ms"],
                last_success=info.get("last_success"),
            )
        return DependencyHealthResponse(
            status=raw_health["status"],
            timestamp=raw_health["timestamp"],
            dependencies=dep_dict,
        )

    def get_slo_evaluation(self) -> SLOSummaryResponse:
        """Evaluate operational SLOs and calculate remaining error budgets."""
        results = self.slo_evaluator.evaluate_slos()
        slo_items: list[SLOResponseItem] = []
        overall = "MET"

        for res in results:
            if res.status == "BREACHED":
                overall = "BREACHED"
            elif res.status == "WARNING" and overall != "BREACHED":
                overall = "WARNING"

            slo_items.append(
                SLOResponseItem(
                    name=res.name,
                    target=res.target,
                    observed=round(res.observed, 4),
                    status=res.status,
                    error_budget_remaining=round(res.error_budget_remaining, 4),
                )
            )

        return SLOSummaryResponse(overall_status=overall, slos=slo_items)

    def get_active_alerts(self) -> AlertsResponse:
        """Scan current metrics against defined alert thresholds."""
        active_list = self.slo_evaluator.evaluate_alerts()
        items = [
            AlertResponseItem(
                name=alert.condition_name,
                severity=alert.severity,
                message=alert.message,
                observed_value=round(alert.observed_value, 4),
                threshold=round(alert.threshold, 4),
                is_active=True,
            )
            for alert in active_list
        ]
        return AlertsResponse(total_active=len(items), alerts=items)

    def get_trace_detail(
        self, trace_id: str, tenant_org_id: UUID | None = None
    ) -> TraceDetailResponse | None:
        """Retrieve recorded spans for trace with tenant boundary isolation check."""
        spans = self.trace_manager.get_trace_spans(trace_id)
        if not spans:
            return None

        # Tenant boundary check: if spans contain organization_id attribute, ensure it matches tenant_org_id
        if tenant_org_id is not None:
            for span in spans:
                span_org = span.attributes.get("organization_id")
                if span_org and str(span_org) != str(tenant_org_id):
                    raise ObservabilityAuthorizationError(
                        f"Access denied: trace belongs to tenant {span_org}"
                    )

        span_items = [
            TraceSpanResponseItem(
                span_id=s.span_id,
                trace_id=s.trace_id,
                parent_span_id=s.parent_span_id,
                name=s.name,
                kind=str(s.kind),
                duration_ms=round(s.duration_ms, 2),
                status=str(s.status),
                attributes=s.attributes,
            )
            for s in spans
        ]
        return TraceDetailResponse(trace_id=trace_id, spans=span_items)


# Global singleton
_global_observability_service: ObservabilityService | None = None


def get_observability_service() -> ObservabilityService:
    """Singleton getter for ObservabilityService."""
    global _global_observability_service
    if _global_observability_service is None:
        _global_observability_service = ObservabilityService()
    return _global_observability_service
