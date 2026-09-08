"""Domain error definitions for Knowledge Graph operations and violations."""

from typing import Any
from uuid import UUID


class KnowledgeGraphError(Exception):
    """Base exception for all knowledge graph domain errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GraphNodeNotFoundError(KnowledgeGraphError):
    """Raised when a referenced graph node cannot be found in the tenant's graph."""

    def __init__(self, node_id: UUID, organization_id: UUID) -> None:
        super().__init__(
            f"Knowledge graph node '{node_id}' not found for organization '{organization_id}'.",
            {"node_id": str(node_id), "organization_id": str(organization_id)},
        )


class GraphEdgeNotFoundError(KnowledgeGraphError):
    """Raised when a referenced graph edge cannot be found in the tenant's graph."""

    def __init__(self, edge_id: UUID, organization_id: UUID) -> None:
        super().__init__(
            f"Knowledge graph edge '{edge_id}' not found for organization '{organization_id}'.",
            {"edge_id": str(edge_id), "organization_id": str(organization_id)},
        )


class CrossTenantGraphViolationError(KnowledgeGraphError):
    """Raised when an operation attempts to link or traverse nodes across tenant boundaries."""

    def __init__(self, reason: str, organization_id: UUID) -> None:
        super().__init__(
            f"Cross-tenant graph boundary violation: {reason}",
            {"organization_id": str(organization_id)},
        )


class GraphTraversalBudgetExceededError(KnowledgeGraphError):
    """Raised when a graph traversal exceeds depth, node count, or edge count limits."""

    def __init__(
        self, limit_name: str, limit_value: int | float, actual_value: int | float
    ) -> None:
        super().__init__(
            f"Graph traversal budget exceeded for {limit_name}: max {limit_value}, reached {actual_value}.",
            {
                "limit_name": limit_name,
                "limit_value": limit_value,
                "actual_value": actual_value,
            },
        )


class CyclicGraphError(KnowledgeGraphError):
    """Raised or flagged when an unhandled or invalid cycle is encountered."""

    def __init__(self, cycle_path: list[str]) -> None:
        super().__init__(
            f"Cycle detected in knowledge graph path: {' -> '.join(cycle_path)}",
            {"cycle_path": cycle_path},
        )


class UnverifiedRelationshipError(KnowledgeGraphError):
    """Raised when an unverified relationship is used in a context demanding verified edges."""

    def __init__(self, edge_id: UUID) -> None:
        super().__init__(
            f"Relationship edge '{edge_id}' is not verified and cannot be used in trusted context.",
            {"edge_id": str(edge_id)},
        )


class EntityResolutionError(KnowledgeGraphError):
    """Raised when deterministic entity resolution fails or reaches an ambiguous state."""

    def __init__(self, entity_text: str, reason: str) -> None:
        super().__init__(
            f"Failed to resolve entity '{entity_text}': {reason}",
            {"entity_text": entity_text, "reason": reason},
        )


class GraphPublishingError(KnowledgeGraphError):
    """Raised when a node or edge cannot transition to published state."""

    def __init__(self, object_id: UUID, current_status: str) -> None:
        super().__init__(
            f"Cannot publish graph object '{object_id}' currently in state '{current_status}'.",
            {"object_id": str(object_id), "current_status": current_status},
        )
