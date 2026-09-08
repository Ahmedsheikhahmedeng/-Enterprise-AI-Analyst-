"""Application service coordinating bounded graph traversals and neighborhood discovery."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import GraphEdgeType
from app.knowledge_graph.domain.models import GraphBudget, GraphNode, GraphTraversal
from app.knowledge_graph.infrastructure.adjacency import AdjacencyEngine
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.observability.instrumentation.knowledge_graph import (
    get_knowledge_graph_instrumentation,
)


class TraversalService:
    """Performs bounded graph traversal enforcing max_depth, max_nodes, and tenant isolation."""

    def __init__(
        self,
        session: AsyncSession,
        budget: GraphBudget | None = None,
    ) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)
        self.budget = budget or GraphBudget()
        self.adjacency_engine = AdjacencyEngine(self.budget)
        self.instrumentation = get_knowledge_graph_instrumentation()

    async def get_neighbors(
        self,
        node_id: UUID,
        organization_id: UUID,
        depth: int = 1,
        edge_types: list[GraphEdgeType] | None = None,
        only_published: bool = True,
    ) -> GraphTraversal:
        """Traverse neighborhood of a specific node up to max_depth (capped at 4)."""
        # 1. Fetch tenant edges
        edges = await self.repo.list_edges(
            organization_id=organization_id,
            only_published=only_published,
            limit=self.budget.max_edges,
        )

        # 2. Fetch tenant nodes
        nodes = await self.repo.list_nodes(
            organization_id=organization_id,
            limit=self.budget.max_nodes,
        )
        nodes_by_id: dict[UUID, GraphNode] = {n.id: n for n in nodes}

        # 3. Perform bounded traversal
        traversal = self.adjacency_engine.traverse(
            start_node_id=node_id,
            edges=edges,
            nodes_by_id=nodes_by_id,
            max_depth=depth,
            max_nodes=self.budget.max_nodes,
            edge_types=edge_types,
        )

        # 4. Record telemetry
        self.instrumentation.record_traversal(
            depth=min(depth, self.budget.max_depth),
            nodes_visited=len(traversal.visited_nodes),
            edges_visited=len(traversal.visited_edges),
            status="success",
        )

        return traversal
