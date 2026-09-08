"""Protocol interfaces for Knowledge Graph repository, adjacency engine, and services."""

from typing import Protocol
from uuid import UUID

from app.knowledge_graph.domain.enums import GraphEdgeType, GraphNodeType, GraphStatus
from app.knowledge_graph.domain.models import (
    EntityResolutionResult,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphQueryResult,
    GraphTraversal,
)


class KnowledgeGraphRepositoryProtocol(Protocol):
    """Abstract interface for knowledge graph storage operations."""

    async def get_node(self, node_id: UUID, organization_id: UUID) -> GraphNode | None: ...

    async def get_node_by_source(
        self, organization_id: UUID, source_object_type: str, source_object_id: UUID
    ) -> GraphNode | None: ...

    async def list_nodes(
        self,
        organization_id: UUID,
        node_type: GraphNodeType | None = None,
        status: GraphStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GraphNode]: ...

    async def get_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge | None: ...

    async def list_edges(
        self,
        organization_id: UUID,
        source_node_id: UUID | None = None,
        target_node_id: UUID | None = None,
        edge_type: GraphEdgeType | None = None,
        only_published: bool = True,
        only_verified: bool = False,
    ) -> list[GraphEdge]: ...

    async def get_graph_version(self, organization_id: UUID) -> int: ...

    async def bump_graph_version(self, organization_id: UUID) -> int: ...


class AdjacencyEngineProtocol(Protocol):
    """Protocol for graph neighbor indexing and bounded path traversal."""

    def build_adjacency(
        self, edges: list[GraphEdge]
    ) -> dict[UUID, list[tuple[UUID, GraphEdge]]]: ...

    def find_paths(
        self,
        start_node_id: UUID,
        target_node_id: UUID,
        edges: list[GraphEdge],
        nodes_by_id: dict[UUID, GraphNode],
        max_depth: int = 4,
        max_paths: int = 10,
    ) -> list[GraphPath]: ...

    def traverse(
        self,
        start_node_id: UUID,
        edges: list[GraphEdge],
        nodes_by_id: dict[UUID, GraphNode],
        max_depth: int = 4,
        max_nodes: int = 500,
    ) -> GraphTraversal: ...


class EntityResolutionProtocol(Protocol):
    """Protocol for resolving natural language references to graph entities."""

    async def resolve(self, text: str, organization_id: UUID) -> EntityResolutionResult: ...


class GraphQueryPlannerProtocol(Protocol):
    """Protocol for compiling natural language questions to graph reasoning plans."""

    async def plan(self, question: str, organization_id: UUID) -> GraphQueryResult: ...
