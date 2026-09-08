"""Service Level Objective (SLO) definitions, evaluation engine, and error budget accounting."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry
from app.observability.models import (
    ActiveAlert,
    AlertCondition,
    ErrorBudget,
    SLODefinition,
    SLOResult,
)


class SLOEvaluator:
    """Evaluates operational Service Level Objectives and calculates remaining error budgets."""

    DEFAULT_SLOS: tuple[SLODefinition, ...] = (
        SLODefinition(
            name="analyst_availability",
            description="Overall availability and success rate of Analyst workflows",
            target=0.99,  # 99%
            metric_name="enterprise_ai_analyst_requests_total",
            comparison=">=",
        ),
        SLODefinition(
            name="analyst_p95_latency",
            description="P95 latency of Analyst workflows",
            target=3000.0,  # 3000ms
            metric_name="enterprise_ai_analyst_duration_ms",
            comparison="<=",
        ),
        SLODefinition(
            name="sql_success_rate",
            description="Proportion of successful Text-to-SQL query executions",
            target=0.98,  # 98%
            metric_name="enterprise_ai_sql_queries_total",
            comparison=">=",
        ),
        SLODefinition(
            name="rag_success_rate",
            description="Proportion of non-empty grounded RAG generation runs",
            target=0.95,  # 95%
            metric_name="enterprise_ai_rag_requests_total",
            comparison=">=",
        ),
        SLODefinition(
            name="llm_success_rate",
            description="Availability and reliability of LLM inference requests",
            target=0.99,  # 99%
            metric_name="enterprise_ai_llm_requests_total",
            comparison=">=",
        ),
    )

    DEFAULT_ALERTS: tuple[AlertCondition, ...] = (
        AlertCondition(
            name="high_error_rate",
            condition_type="error_rate",
            threshold=0.05,  # > 5% error rate
            severity="CRITICAL",
            description="Platform HTTP error rate exceeds 5%",
        ),
        AlertCondition(
            name="high_p95_latency",
            condition_type="latency",
            threshold=5000.0,  # > 5000ms
            severity="WARNING",
            description="Platform P95 latency exceeds 5,000ms",
        ),
        AlertCondition(
            name="llm_provider_failure_rate",
            condition_type="error_rate",
            threshold=0.10,  # > 10% failure
            severity="CRITICAL",
            description="LLM provider call failure rate exceeds 10%",
        ),
    )

    def __init__(
        self,
        registry: MetricsRegistry | None = None,
        slos: tuple[SLODefinition, ...] | None = None,
        alerts: tuple[AlertCondition, ...] | None = None,
    ) -> None:
        self.registry = registry or get_metrics_registry()
        self.slos = slos or self.DEFAULT_SLOS
        self.alert_definitions = alerts or self.DEFAULT_ALERTS

    def calculate_error_budget(
        self, target: float, observed: float, comparison: str = ">="
    ) -> ErrorBudget:
        """Calculate deterministic remaining error budget normalized between -1.0 and 1.0."""
        if comparison == ">=":
            total_allowed_bad_ratio = max(0.0001, 1.0 - target)
            actual_bad_ratio = max(0.0, 1.0 - observed)
            budget_remaining = 1.0 - (actual_bad_ratio / total_allowed_bad_ratio)

            if budget_remaining >= 0.20:
                status = "MET"
            elif budget_remaining >= 0.0:
                status = "WARNING"
            else:
                status = "BREACHED"

            return ErrorBudget(
                target=target,
                observed=observed,
                budget_remaining=budget_remaining,
                status=status,
            )
        else:
            # Latency (<= target)
            if observed <= target:
                margin = (target - observed) / target
                status = "MET" if margin >= 0.1 else "WARNING"
                budget_remaining = margin
            else:
                margin = (target - observed) / target
                status = "BREACHED"
                budget_remaining = margin

            return ErrorBudget(
                target=target,
                observed=observed,
                budget_remaining=budget_remaining,
                status=status,
            )

    def evaluate_slos(self) -> list[SLOResult]:
        """Evaluate all active SLO definitions against metrics in the registry."""
        results: list[SLOResult] = []
        metrics_data = self.registry.get_all_metrics()
        counters = metrics_data["counters"]
        histograms = metrics_data["histograms"]

        for slo in self.slos:
            observed = 1.0  # default when no requests have occurred

            if slo.name == "analyst_availability":
                total = sum(
                    item["value"]
                    for item in counters.get("enterprise_ai_analyst_requests_total", [])
                )
                success = sum(
                    item["value"]
                    for item in counters.get("enterprise_ai_analyst_success_total", [])
                )
                observed = (success / total) if total > 0 else 1.0

            elif slo.name == "sql_success_rate":
                total = sum(
                    item["value"] for item in counters.get("enterprise_ai_sql_queries_total", [])
                )
                failures = sum(
                    item["value"]
                    for item in counters.get("enterprise_ai_sql_query_failures_total", [])
                )
                observed = ((total - failures) / total) if total > 0 else 1.0

            elif slo.name == "rag_success_rate":
                total = sum(
                    item["value"] for item in counters.get("enterprise_ai_rag_requests_total", [])
                )
                failures = sum(
                    item["value"] for item in counters.get("enterprise_ai_rag_failures_total", [])
                )
                observed = ((total - failures) / total) if total > 0 else 1.0

            elif slo.name == "llm_success_rate":
                total = sum(
                    item["value"] for item in counters.get("enterprise_ai_llm_requests_total", [])
                )
                failures = sum(
                    item["value"] for item in counters.get("enterprise_ai_llm_failures_total", [])
                )
                observed = ((total - failures) / total) if total > 0 else 1.0

            elif slo.name == "analyst_p95_latency":
                hist = histograms.get("enterprise_ai_analyst_duration_ms", [])
                if hist and hist[0]["count"] > 0:
                    observed = hist[0]["sum"] / hist[0]["count"]
                else:
                    observed = 100.0

            budget = self.calculate_error_budget(slo.target, observed, slo.comparison)
            results.append(
                SLOResult(
                    name=slo.name,
                    description=slo.description,
                    target=slo.target,
                    observed=observed,
                    status=budget.status,
                    error_budget_remaining=budget.budget_remaining,
                )
            )

        return results

    def evaluate_alerts(self) -> list[ActiveAlert]:
        """Scan current metrics against defined alert thresholds."""
        active: list[ActiveAlert] = []
        metrics_data = self.registry.get_all_metrics()
        counters = metrics_data["counters"]

        http_total = sum(
            item["value"] for item in counters.get("enterprise_ai_http_requests_total", [])
        )
        http_errors = sum(
            item["value"] for item in counters.get("enterprise_ai_http_errors_total", [])
        )
        error_rate = (http_errors / http_total) if http_total > 0 else 0.0

        for cond in self.alert_definitions:
            if (
                cond.condition_type == "error_rate"
                and cond.name == "high_error_rate"
                and error_rate > cond.threshold
            ):
                active.append(
                    ActiveAlert(
                        alert_id=f"alert-{cond.name}",
                        condition_name=cond.name,
                        severity=cond.severity,
                        observed_value=error_rate,
                        threshold=cond.threshold,
                        message=f"HTTP error rate is {error_rate * 100:.1f}%, exceeding {cond.threshold * 100:.1f}% threshold.",
                    )
                )

        return active
