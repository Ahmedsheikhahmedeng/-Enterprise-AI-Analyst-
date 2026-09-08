"""Domain entities, dataclasses, and value objects for the Knowledge Graph."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.knowledge_graph.domain.enums import (
    ConflictSeverity,
    ConflictStatus,
    GraphEdgeType,
    GraphNodeType,
    GraphStatus,
    ResolutionStatus,
)


@dataclass
class GraphNode:
    """Domain representation of a knowledge graph vertex."""

    id: UUID
    organization_id: UUID
    node_type: GraphNodeType
    name: str
    normalized_name: str
    source_object_type: str
    source_object_id: UUID
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    status: GraphStatus = GraphStatus.DRAFT
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class GraphEdge:
    """Domain representation of a directed knowledge graph relationship."""

    id: UUID
    organization_id: UUID
    source_node_id: UUID
    target_node_id: UUID
    edge_type: GraphEdgeType
    weight: float = 1.0
    confidence: float = 1.0
    is_verified: bool = False
    status: GraphStatus = GraphStatus.DRAFT
    source_object_type: str | None = None
    source_object_id: UUID | None = None
    version: int = 1
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class GraphPath:
    """Represents a bounded traversal path between two nodes in the graph."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    depth: int
    confidence: float
    verified_ratio: float

    @property
    def start_node(self) -> GraphNode | None:
        return self.nodes[0] if self.nodes else None

    @property
    def end_node(self) -> GraphNode | None:
        return self.nodes[-1] if self.nodes else None


@dataclass
class GraphTraversal:
    """Captures the visited nodes, edges, and discovered paths from a traversal run."""

    visited_nodes: list[GraphNode]
    visited_edges: list[GraphEdge]
    depth: int
    paths: list[GraphPath] = field(default_factory=list)


@dataclass
class GraphEntityAlias:
    """Domain representation of an alias mapped to an entity node."""

    id: UUID
    organization_id: UUID
    entity_node_id: UUID
    alias: str
    normalized_alias: str
    language: str = "en"
    source: str = "user"
    is_verified: bool = False
    created_at: datetime | None = None


@dataclass
class EntityResolutionResult:
    """Structured outcome from resolving a text term against graph entities."""

    status: ResolutionStatus
    entity_node_id: UUID | None
    entity_name: str | None
    confidence: float
    candidate_ids: list[UUID] = field(default_factory=list)
    reason: str = ""


@dataclass
class GraphQuery:
    """Input parameters for structured graph relationship querying."""

    start_entity: str | None = None
    target_concept: str | None = None
    start_node_ids: list[UUID] | None = None
    target_node_ids: list[UUID] | None = None
    max_depth: int = 3
    edge_types: list[GraphEdgeType] | None = None
    min_confidence: float = 0.0
    only_published: bool = True
    only_verified: bool = False


@dataclass
class GraphProvenance:
    """Detailed audit and reproducibility metadata for a graph reasoning result."""

    organization_id: UUID
    graph_version: int
    node_ids: list[UUID]
    edge_ids: list[UUID]
    source_object_ids: list[UUID]
    verified_status: bool
    confidence: float


@dataclass
class GraphQueryResult:
    """Execution output from a graph traversal or concept reasoning query."""

    paths: list[GraphPath]
    confidence: float
    provenance: GraphProvenance
    resolved_entities: list[dict[str, Any]] = field(default_factory=list)
    resolved_metrics: list[dict[str, Any]] = field(default_factory=list)
    resolved_dimensions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class GraphConflict:
    """Domain model capturing incompatible or competing relationships."""

    id: UUID
    organization_id: UUID
    reason: str
    severity: ConflictSeverity
    node_ids: list[UUID]
    edge_ids: list[UUID]
    status: ConflictStatus
    created_at: datetime | None = None
    resolved_at: datetime | None = None
    resolved_by: UUID | None = None


@dataclass
class GraphBudget:
    """Enforces upper limits on graph exploration and query planning."""

    max_graph_queries: int = 50
    max_depth: int = 4
    max_nodes: int = 500
    max_edges: int = 1000
    max_paths: int = 100
    max_execution_ms: float = 5000.0
