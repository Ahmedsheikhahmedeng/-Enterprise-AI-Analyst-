"""Observability instrumentation, metrics, and audit event definitions for Knowledge Graph."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry

# Audit Event Identifiers
AUDIT_GRAPH_NODE_CREATED = "GRAPH_NODE_CREATED"
AUDIT_GRAPH_NODE_UPDATED = "GRAPH_NODE_UPDATED"
AUDIT_GRAPH_EDGE_CREATED = "GRAPH_EDGE_CREATED"
AUDIT_GRAPH_EDGE_UPDATED = "GRAPH_EDGE_UPDATED"
AUDIT_GRAPH_EDGE_VERIFIED = "GRAPH_EDGE_VERIFIED"
AUDIT_GRAPH_QUERY_EXECUTED = "GRAPH_QUERY_EXECUTED"
AUDIT_GRAPH_PUBLISHED = "GRAPH_PUBLISHED"
AUDIT_GRAPH_ARCHIVED = "GRAPH_ARCHIVED"
AUDIT_GRAPH_CONFLICT_DETECTED = "GRAPH_CONFLICT_DETECTED"


class KnowledgeGraphInstrumentation:
    """Provides low-cardinality Prometheus metrics and operational telemetry for Knowledge Graph."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self.registry = registry or get_metrics_registry()

    def record_query(
        self,
        graph_operation: str,
        status: str,
        duration_s: float | None = None,
    ) -> None:
        labels = {"graph_operation": graph_operation, "status": status}
        self.registry.increment(
            "graph_query_total",
            value=1.0,
            labels=labels,
            description="Total count of knowledge graph queries executed",
        )
        if duration_s is not None:
            self.registry.observe(
                "graph_query_latency_seconds",
                value=duration_s,
                labels={"graph_operation": graph_operation},
                description="Duration of knowledge graph queries in seconds",
            )

    def record_traversal(
        self,
        depth: int,
        nodes_visited: int,
        edges_visited: int,
        status: str = "success",
    ) -> None:
        self.registry.increment(
            "graph_traversal_total",
            value=1.0,
            labels={"status": status},
            description="Total count of graph traversals performed",
        )
        self.registry.observe(
            "graph_traversal_depth",
            value=float(depth),
            labels={"status": status},
            description="Depth reached during graph traversals",
        )
        self.registry.increment(
            "graph_nodes_visited_total",
            value=float(nodes_visited),
            labels={"status": status},
            description="Total count of nodes visited during traversals",
        )
        self.registry.increment(
            "graph_edges_visited_total",
            value=float(edges_visited),
            labels={"status": status},
            description="Total count of edges visited during traversals",
        )

    def record_path_resolution_success(self, edge_type: str) -> None:
        self.registry.increment(
            "graph_path_resolution_success_total",
            value=1.0,
            labels={"edge_type": edge_type},
            description="Total count of successfully resolved graph paths",
        )

    def record_resolution_ambiguous(self, node_type: str) -> None:
        self.registry.increment(
            "graph_resolution_ambiguous_total",
            value=1.0,
            labels={"node_type": node_type},
            description="Total count of ambiguous entity or path resolutions",
        )

    def record_conflict(self, status: str) -> None:
        self.registry.increment(
            "graph_conflict_total",
            value=1.0,
            labels={"status": status},
            description="Total count of structural collisions or graph conflicts detected",
        )


_knowledge_graph_instrumentation: KnowledgeGraphInstrumentation | None = None


def get_knowledge_graph_instrumentation() -> KnowledgeGraphInstrumentation:
    """Returns singleton instance of KnowledgeGraphInstrumentation."""
    global _knowledge_graph_instrumentation
    if _knowledge_graph_instrumentation is None:
        _knowledge_graph_instrumentation = KnowledgeGraphInstrumentation()
    return _knowledge_graph_instrumentation
