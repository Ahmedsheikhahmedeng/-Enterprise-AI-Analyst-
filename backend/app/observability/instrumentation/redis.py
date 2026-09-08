"""Low-overhead Redis cache operational instrumentation."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class RedisInstrumentation:
    """Measures Redis cache operations and latency without capturing key or payload contents."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        """Record a Redis cache command execution."""
        clean_op = operation.lower().strip()
        status_str = "ok" if success else "error"
        labels = {"operation": clean_op, "status": status_str}

        self.metrics.increment(
            "redis_operations_total",
            value=1.0,
            labels=labels,
            description="Total Redis operations executed",
        )
        self.metrics.observe(
            "redis_operation_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Redis operation latency in milliseconds",
        )

        if not success:
            err_labels = {"operation": clean_op, "error_type": error_type or "unknown"}
            self.metrics.increment(
                "redis_operation_errors_total",
                value=1.0,
                labels=err_labels,
                description="Total failed Redis operations",
            )


# Global singleton
_global_redis_instrumentation: RedisInstrumentation | None = None


def get_redis_instrumentation() -> RedisInstrumentation:
    """Singleton getter for RedisInstrumentation."""
    global _global_redis_instrumentation
    if _global_redis_instrumentation is None:
        _global_redis_instrumentation = RedisInstrumentation()
    return _global_redis_instrumentation
