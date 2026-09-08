"""Low-overhead Qdrant vector database operational instrumentation."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class QdrantInstrumentation:
    """Measures Qdrant vector search operations and latency without capturing vector embeddings or document payloads."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        error_type: str | None = None,
    ) -> None:
        """Record a Qdrant vector search or mutation operation."""
        clean_op = operation.lower().strip()
        status_str = "ok" if success else "error"
        labels = {"operation": clean_op, "status": status_str}

        self.metrics.increment(
            "qdrant_operations_total",
            value=1.0,
            labels=labels,
            description="Total Qdrant operations executed",
        )
        self.metrics.observe(
            "qdrant_operation_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Qdrant operation latency in milliseconds",
        )

        if not success:
            err_labels = {"operation": clean_op, "error_type": error_type or "unknown"}
            self.metrics.increment(
                "qdrant_operation_errors_total",
                value=1.0,
                labels=err_labels,
                description="Total failed Qdrant operations",
            )


# Global singleton
_global_qdrant_instrumentation: QdrantInstrumentation | None = None


def get_qdrant_instrumentation() -> QdrantInstrumentation:
    """Singleton getter for QdrantInstrumentation."""
    global _global_qdrant_instrumentation
    if _global_qdrant_instrumentation is None:
        _global_qdrant_instrumentation = QdrantInstrumentation()
    return _global_qdrant_instrumentation
