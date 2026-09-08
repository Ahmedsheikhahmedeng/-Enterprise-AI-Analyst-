"""Deep instrumentation for the AI Analyst orchestration pipeline."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class AnalystInstrumentation:
    """Instruments Analyst orchestration stages, routing distribution, and latency."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_analyst_request(
        self,
        route: str,
        status: str,
        language: str,
        duration_ms: float,
        is_degraded: bool = False,
    ) -> None:
        """Record overall analyst request execution and outcome."""
        clean_route = route.lower() if route else "none"
        clean_status = status.lower() if status else "unknown"
        clean_lang = language.lower() if language else "unknown"

        labels = {
            "route": clean_route,
            "status": clean_status,
            "language": clean_lang,
        }

        # 1. Total requests
        self.metrics.increment(
            "analyst_requests_total",
            value=1.0,
            labels=labels,
            description="Total AI Analyst requests handled",
        )
        self.metrics.increment(
            "enterprise_ai_analyst_requests_total",
            value=1.0,
            labels=labels,
            description="Enterprise AI total analyst requests handled",
        )

        # 2. Route distribution
        self.metrics.increment(
            "analyst_route_total",
            value=1.0,
            labels={"route": clean_route},
            description="Routing choices taken by Analyst pipeline",
        )

        # 3. Success / Failure / Degraded
        if clean_status == "success" or clean_status == "ok":
            self.metrics.increment(
                "analyst_success_total",
                value=1.0,
                labels={"route": clean_route, "language": clean_lang},
                description="Successful analyst request executions",
            )
            self.metrics.increment(
                "enterprise_ai_analyst_success_total",
                value=1.0,
                labels={"route": clean_route, "language": clean_lang},
                description="Enterprise AI successful analyst request executions",
            )
        elif clean_status == "failure" or clean_status == "error":
            self.metrics.increment(
                "analyst_failure_total",
                value=1.0,
                labels={"route": clean_route, "language": clean_lang},
                description="Failed analyst request executions",
            )
            self.metrics.increment(
                "enterprise_ai_analyst_failure_total",
                value=1.0,
                labels={"route": clean_route, "language": clean_lang},
                description="Enterprise AI failed analyst request executions",
            )

        if is_degraded:
            self.metrics.increment(
                "analyst_degraded_total",
                value=1.0,
                labels={"route": clean_route},
                description="Degraded analyst executions (e.g. fallback or partial answer)",
            )

        # 4. Latency
        self.metrics.observe(
            "analyst_duration_ms",
            value=duration_ms,
            labels={"route": clean_route, "status": clean_status},
            description="End-to-end Analyst execution latency in milliseconds",
        )

    def record_stage_latency(
        self, stage_name: str, duration_ms: float, route: str = "hybrid"
    ) -> None:
        """Record granular stage execution time (planning, sql, rag, merge, conflict, generation, validation)."""
        clean_stage = stage_name.lower().strip()
        clean_route = route.lower().strip()
        self.metrics.observe(
            f"analyst_stage_{clean_stage}_duration_ms",
            value=duration_ms,
            labels={"stage": clean_stage, "route": clean_route},
            description=f"Analyst stage {clean_stage} latency in milliseconds",
        )


# Global singleton
_global_analyst_instrumentation: AnalystInstrumentation | None = None


def get_analyst_instrumentation() -> AnalystInstrumentation:
    """Singleton getter for AnalystInstrumentation."""
    global _global_analyst_instrumentation
    if _global_analyst_instrumentation is None:
        _global_analyst_instrumentation = AnalystInstrumentation()
    return _global_analyst_instrumentation
