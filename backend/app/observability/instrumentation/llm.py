"""Deep instrumentation for LLM provider requests, token usage, and cost tracking."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class LLMInstrumentation:
    """Instruments LLM request latency, token consumption, cost calculations, and provider health."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_llm_call(
        self,
        provider: str,
        model: str,
        operation: str,
        status: str,
        duration_ms: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        is_timeout: bool = False,
    ) -> None:
        """Record an LLM provider invocation with strict high-cardinality protection."""
        clean_provider = provider.lower().strip() if provider else "unknown"
        clean_model = model.lower().strip() if model else "unknown"
        clean_op = operation.lower().strip() if operation else "general"
        clean_status = status.lower().strip() if status else "unknown"

        labels = {
            "provider": clean_provider,
            "model": clean_model,
            "operation": clean_op,
            "status": clean_status,
        }

        # 1. Request counters
        self.metrics.increment(
            "llm_requests_total",
            value=1.0,
            labels=labels,
            description="Total LLM API requests executed",
        )
        self.metrics.increment(
            "enterprise_ai_llm_requests_total",
            value=1.0,
            labels=labels,
            description="Enterprise AI total LLM requests executed",
        )

        if clean_status == "ok" or clean_status == "success":
            self.metrics.increment(
                "llm_success_total",
                value=1.0,
                labels={"provider": clean_provider, "model": clean_model},
                description="Successful LLM API requests",
            )
            self.metrics.increment(
                "enterprise_ai_llm_success_total",
                value=1.0,
                labels={"provider": clean_provider, "model": clean_model},
                description="Enterprise AI successful LLM API requests",
            )
        else:
            self.metrics.increment(
                "llm_failures_total",
                value=1.0,
                labels={"provider": clean_provider, "model": clean_model},
                description="Failed LLM API requests",
            )
            self.metrics.increment(
                "enterprise_ai_llm_failures_total",
                value=1.0,
                labels={"provider": clean_provider, "model": clean_model},
                description="Enterprise AI failed LLM API requests",
            )

        # 2. Duration latency
        self.metrics.observe(
            "llm_duration_ms",
            value=duration_ms,
            labels={"provider": clean_provider, "model": clean_model, "operation": clean_op},
            description="LLM provider latency in milliseconds",
        )

        # 3. Token counts
        total_tokens = input_tokens + output_tokens
        if input_tokens > 0:
            self.metrics.increment(
                "llm_input_tokens",
                value=float(input_tokens),
                labels={"provider": clean_provider, "model": clean_model},
                description="Total LLM prompt/input tokens consumed",
            )
        if output_tokens > 0:
            self.metrics.increment(
                "llm_output_tokens",
                value=float(output_tokens),
                labels={"provider": clean_provider, "model": clean_model},
                description="Total LLM completion/output tokens generated",
            )
        if total_tokens > 0:
            self.metrics.increment(
                "llm_total_tokens",
                value=float(total_tokens),
                labels={"provider": clean_provider, "model": clean_model},
                description="Total cumulative LLM tokens processed",
            )
            self.metrics.increment(
                "enterprise_ai_llm_tokens_total",
                value=float(total_tokens),
                labels={"provider": clean_provider, "model": clean_model},
                description="Enterprise AI cumulative LLM tokens processed",
            )

        # 4. Cost tracking
        if cost_usd > 0.0:
            self.metrics.increment(
                "llm_cost_total",
                value=cost_usd,
                labels={"provider": clean_provider, "model": clean_model},
                description="Cumulative estimated LLM cost in USD",
            )
            self.metrics.increment(
                "enterprise_ai_llm_cost_total",
                value=cost_usd,
                labels={"provider": clean_provider, "model": clean_model},
                description="Enterprise AI cumulative LLM cost in USD",
            )
            self.metrics.increment(
                "ai_cost_total",
                value=cost_usd,
                labels={},
                description="Total AI platform expenditure in USD",
            )
            self.metrics.increment(
                "ai_cost_by_provider",
                value=cost_usd,
                labels={"provider": clean_provider},
                description="AI cost aggregated by provider in USD",
            )
            self.metrics.increment(
                "ai_cost_by_model",
                value=cost_usd,
                labels={"model": clean_model},
                description="AI cost aggregated by model in USD",
            )
            self.metrics.increment(
                "ai_cost_by_operation",
                value=cost_usd,
                labels={"operation": clean_op},
                description="AI cost aggregated by pipeline operation in USD",
            )

        # 5. Timeout tracking
        if is_timeout:
            self.metrics.increment(
                "llm_timeout_total",
                value=1.0,
                labels={"provider": clean_provider, "model": clean_model},
                description="Total LLM requests timing out",
            )


# Global singleton
_global_llm_instrumentation: LLMInstrumentation | None = None


def get_llm_instrumentation() -> LLMInstrumentation:
    """Singleton getter for LLMInstrumentation."""
    global _global_llm_instrumentation
    if _global_llm_instrumentation is None:
        _global_llm_instrumentation = LLMInstrumentation()
    return _global_llm_instrumentation
