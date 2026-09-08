"""Deep instrumentation for Enterprise Agent Memory."""

from functools import lru_cache

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class MemoryInstrumentation:
    """Instruments memory reads, writes, searches, context tokens, conflicts, and deletions."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_memory_write(self, memory_type: str, status: str = "success") -> None:
        self.metrics.increment(
            "memory_writes_total",
            value=1.0,
            labels={"memory_type": memory_type.lower(), "status": status.lower()},
            description="Total memory persistence events",
        )

    def record_memory_read(self, memory_type: str, status: str = "success") -> None:
        self.metrics.increment(
            "memory_reads_total",
            value=1.0,
            labels={"memory_type": memory_type.lower(), "status": status.lower()},
            description="Total memory retrieval events",
        )

    def record_memory_delete(self, status: str = "success") -> None:
        self.metrics.increment(
            "memory_deletes_total",
            value=1.0,
            labels={"status": status.lower()},
            description="Total memory deletion events",
        )

    def record_memory_search(
        self, duration_ms: float, hits_count: int, status: str = "success"
    ) -> None:
        labels = {"status": status.lower()}
        self.metrics.increment(
            "memory_searches_total",
            value=1.0,
            labels=labels,
            description="Total memory search queries executed",
        )
        self.metrics.observe(
            "memory_retrieval_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Latency of memory search operations in milliseconds",
        )
        if hits_count > 0:
            self.metrics.increment(
                "agent_memory_hits_total",
                value=1.0,
                labels=labels,
                description="Total memory searches returning relevant hits",
            )
        else:
            self.metrics.increment(
                "agent_memory_misses_total",
                value=1.0,
                labels=labels,
                description="Total memory searches returning zero hits",
            )

    def record_conflict_detected(self, resolution: str) -> None:
        self.metrics.increment(
            "memory_conflicts_total",
            value=1.0,
            labels={"status": resolution.lower()},
            description="Total memory contradictions/conflicts detected",
        )

    def record_context_tokens(self, token_count: int) -> None:
        self.metrics.observe(
            "memory_context_tokens",
            value=float(token_count),
            labels={"status": "injected"},
            description="Token volume of memory items injected into prompt context",
        )


@lru_cache(maxsize=1)
def get_memory_instrumentation() -> MemoryInstrumentation:
    """Return cached singleton MemoryInstrumentation instance."""
    return MemoryInstrumentation()
