"""Application service computing bounded multi-hop relationship paths between concepts."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import GraphEdgeType
from app.knowledge_graph.domain.models import GraphBudget, GraphNode, GraphPath
from app.knowledge_graph.infrastructure.adjacency import AdjacencyEngine
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.observability.instrumentation.knowledge_graph import (
    get_knowledge_graph_instrumentation,
)


class PathService:
    """Finds ranked paths connecting two entities or concepts within the knowledge graph."""

    def __init__(
        self,
        session: AsyncSession,
        budget: GraphBudget | None = None,
        repo: KnowledgeGraphRepository | None = None,
    ) -> None:
        self.session = session
        self.repo = repo or KnowledgeGraphRepository(session)
        self.budget = budget or GraphBudget()
        self.adjacency_engine = AdjacencyEngine(self.budget)
        self.instrumentation = get_knowledge_graph_instrumentation()

    async def find_paths(
        self,
        start_node_id: UUID,
        target_node_id: UUID,
        organization_id: UUID,
        max_depth: int = 4,
        max_paths: int = 10,
        edge_types: list[GraphEdgeType] | None = None,
        only_published: bool = True,
        only_verified: bool = False,
    ) -> list[GraphPath]:
        """Discover ranked paths connecting start and target nodes."""
        # 1. Fetch tenant edges
        edges = await self.repo.list_edges(
            organization_id=organization_id,
            only_published=only_published,
            only_verified=only_verified,
            limit=self.budget.max_edges,
        )

        # 2. Fetch tenant nodes
        nodes = await self.repo.list_nodes(
            organization_id=organization_id,
            limit=self.budget.max_nodes,
        )
        nodes_by_id: dict[UUID, GraphNode] = {n.id: n for n in nodes}

        # 3. Find bounded paths
        paths = self.adjacency_engine.find_paths(
            start_node_id=start_node_id,
            target_node_id=target_node_id,
            edges=edges,
            nodes_by_id=nodes_by_id,
            max_depth=max_depth,
            max_paths=max_paths,
            edge_types=edge_types,
            only_verified=only_verified,
        )

        # 4. Record telemetry
        if paths:
            top_edge_type = paths[0].edges[0].edge_type.value if paths[0].edges else "unknown"
            self.instrumentation.record_path_resolution_success(top_edge_type)

        return paths
