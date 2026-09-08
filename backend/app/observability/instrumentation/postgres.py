"""Low-overhead PostgreSQL database operational instrumentation."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class PostgresInstrumentation:
    """Measures PostgreSQL operations and latency without capturing sensitive query payloads."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        """Record a database operation."""
        clean_op = operation.lower().strip()
        status_str = "ok" if success else "error"
        labels = {"operation": clean_op, "status": status_str}

        self.metrics.increment(
            "postgres_operations_total",
            value=1.0,
            labels=labels,
            description="Total PostgreSQL driver operations",
        )
        self.metrics.observe(
            "postgres_operation_duration_ms",
            value=duration_ms,
            labels=labels,
            description="PostgreSQL operation latency in milliseconds",
        )

        if not success:
            err_labels = {"operation": clean_op, "error_type": error_type or "unknown"}
            self.metrics.increment(
                "postgres_operation_errors_total",
                value=1.0,
                labels=err_labels,
                description="Total failed PostgreSQL driver operations",
            )


# Global singleton
_global_postgres_instrumentation: PostgresInstrumentation | None = None


def get_postgres_instrumentation() -> PostgresInstrumentation:
    """Singleton getter for PostgresInstrumentation."""
    global _global_postgres_instrumentation
    if _global_postgres_instrumentation is None:
        _global_postgres_instrumentation = PostgresInstrumentation()
    return _global_postgres_instrumentation
