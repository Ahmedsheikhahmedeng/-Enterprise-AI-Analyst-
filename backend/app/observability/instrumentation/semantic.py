"""Observability instrumentation and metrics for Semantic Catalog and Semantic Layer."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry

# Audit Event Identifiers
AUDIT_SEMANTIC_TERM_CREATED = "SEMANTIC_TERM_CREATED"
AUDIT_SEMANTIC_TERM_UPDATED = "SEMANTIC_TERM_UPDATED"
AUDIT_SEMANTIC_METRIC_CREATED = "SEMANTIC_METRIC_CREATED"
AUDIT_SEMANTIC_METRIC_UPDATED = "SEMANTIC_METRIC_UPDATED"
AUDIT_SEMANTIC_MAPPING_CREATED = "SEMANTIC_MAPPING_CREATED"
AUDIT_SEMANTIC_MAPPING_VERIFIED = "SEMANTIC_MAPPING_VERIFIED"
AUDIT_SEMANTIC_OBJECT_PUBLISHED = "SEMANTIC_OBJECT_PUBLISHED"
AUDIT_SEMANTIC_OBJECT_ARCHIVED = "SEMANTIC_OBJECT_ARCHIVED"
AUDIT_SEMANTIC_CONFLICT_DETECTED = "SEMANTIC_CONFLICT_DETECTED"


class SemanticInstrumentation:
    """Provides low-cardinality Prometheus metrics and operational telemetry for semantic layer."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self.registry = registry or get_metrics_registry()

    def record_search(
        self, object_type: str, language: str, duration_s: float | None = None
    ) -> None:
        labels = {"object_type": object_type, "language": language}
        self.registry.increment(
            "semantic_search_total",
            value=1.0,
            labels=labels,
            description="Total count of semantic discovery queries executed",
        )
        if duration_s is not None:
            self.registry.observe(
                "semantic_search_latency_seconds",
                value=duration_s,
                labels={"language": language},
                description="Duration of semantic search queries in seconds",
            )

    def record_resolution_success(self, object_type: str, status: str) -> None:
        self.registry.increment(
            "semantic_resolution_success_total",
            value=1.0,
            labels={"object_type": object_type, "status": status},
            description="Total count of successfully resolved semantic concepts",
        )

    def record_resolution_failure(self, resolution_result: str) -> None:
        self.registry.increment(
            "semantic_resolution_failure_total",
            value=1.0,
            labels={"resolution_result": resolution_result},
            description="Total count of semantic resolution failures or misses",
        )

    def record_mapping_conflict(self, severity: str) -> None:
        self.registry.increment(
            "semantic_mapping_conflict_total",
            value=1.0,
            labels={"severity": severity},
            description="Total count of semantic formula collisions or conflicts detected",
        )

    def record_verified_mapping(self, object_type: str) -> None:
        self.registry.increment(
            "semantic_verified_mapping_total",
            value=1.0,
            labels={"object_type": object_type},
            description="Total count of verified physical-to-semantic column bindings",
        )

    def record_query_plan(self, is_authoritative: bool) -> None:
        self.registry.increment(
            "semantic_query_plan_total",
            value=1.0,
            labels={"is_authoritative": str(is_authoritative).lower()},
            description="Total count of generated semantic query plans",
        )


_semantic_instrumentation: SemanticInstrumentation | None = None


def get_semantic_instrumentation() -> SemanticInstrumentation:
    """Retrieve singleton instance of SemanticInstrumentation."""
    global _semantic_instrumentation
    if _semantic_instrumentation is None:
        _semantic_instrumentation = SemanticInstrumentation()
    return _semantic_instrumentation
