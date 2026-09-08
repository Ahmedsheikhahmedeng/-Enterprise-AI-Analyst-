"""Deep instrumentation for RAG pipeline and hybrid retrieval stages."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class RAGInstrumentation:
    """Instruments RAG requests, candidate generation, reranking, and stage latencies."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_rag_request(
        self,
        duration_ms: float,
        status: str = "ok",
        language: str = "unknown",
        is_empty_context: bool = False,
    ) -> None:
        """Record RAG execution outcome and total duration."""
        clean_status = status.lower()
        clean_lang = language.lower()
        labels = {"language": clean_lang, "status": clean_status}

        self.metrics.increment(
            "rag_requests_total",
            value=1.0,
            labels=labels,
            description="Total RAG requests executed",
        )
        self.metrics.increment(
            "enterprise_ai_rag_requests_total",
            value=1.0,
            labels=labels,
            description="Enterprise AI total RAG requests executed",
        )

        self.metrics.observe(
            "rag_duration_ms",
            value=duration_ms,
            labels=labels,
            description="RAG pipeline execution latency in milliseconds",
        )

        if clean_status != "ok":
            self.metrics.increment(
                "rag_failures_total",
                value=1.0,
                labels=labels,
                description="Total RAG execution failures",
            )
            self.metrics.increment(
                "enterprise_ai_rag_failures_total",
                value=1.0,
                labels=labels,
                description="Enterprise AI total RAG execution failures",
            )

        if is_empty_context:
            self.metrics.increment(
                "rag_empty_context_total",
                value=1.0,
                labels={"language": clean_lang},
                description="RAG requests where retrieval yielded empty context",
            )

    def record_retrieval(
        self,
        duration_ms: float,
        dense_count: int = 0,
        sparse_count: int = 0,
        rrf_count: int = 0,
        reranked_count: int = 0,
        final_returned: int = 0,
    ) -> None:
        """Record detailed candidate retrieval and reranking counts."""
        labels = {"type": "hybrid"}
        self.metrics.increment(
            "retrieval_requests_total",
            value=1.0,
            labels=labels,
            description="Total retrieval operations executed",
        )
        self.metrics.observe(
            "retrieval_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Retrieval operation latency in milliseconds",
        )

        # Candidates breakdown
        self.metrics.increment(
            "retrieval_candidates",
            value=float(dense_count + sparse_count),
            labels=labels,
            description="Total raw retrieval candidates generated",
        )
        self.metrics.increment(
            "retrieval_returned",
            value=float(final_returned),
            labels=labels,
            description="Total final retrieval candidates returned",
        )
        self.metrics.increment(
            "dense_candidates",
            value=float(dense_count),
            labels={},
            description="Dense vector candidates retrieved",
        )
        self.metrics.increment(
            "sparse_candidates",
            value=float(sparse_count),
            labels={},
            description="Sparse keyword candidates retrieved",
        )
        self.metrics.increment(
            "rrf_candidates",
            value=float(rrf_count),
            labels={},
            description="Reciprocal Rank Fusion candidates retained",
        )
        self.metrics.increment(
            "reranked_candidates",
            value=float(reranked_count),
            labels={},
            description="Cross-encoder reranked candidates retained",
        )

        if final_returned == 0:
            self.metrics.increment(
                "retrieval_empty_total",
                value=1.0,
                labels=labels,
                description="Retrieval operations that produced 0 candidates",
            )

    def record_stage_latency(self, stage: str, duration_ms: float) -> None:
        """Record stage latencies: query_understanding, dense_search, sparse_search, rrf, rerank, evidence_selection, generation, grounding_validation."""
        clean_stage = stage.lower().strip()
        self.metrics.observe(
            f"rag_stage_{clean_stage}_duration_ms",
            value=duration_ms,
            labels={"stage": clean_stage},
            description=f"RAG stage {clean_stage} latency in milliseconds",
        )


# Global singleton
_global_rag_instrumentation: RAGInstrumentation | None = None


def get_rag_instrumentation() -> RAGInstrumentation:
    """Singleton getter for RAGInstrumentation."""
    global _global_rag_instrumentation
    if _global_rag_instrumentation is None:
        _global_rag_instrumentation = RAGInstrumentation()
    return _global_rag_instrumentation
