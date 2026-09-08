"""Application service generating forward and reverse concept-to-physical data lineage."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import LineageDirection
from app.knowledge_graph.domain.models import GraphBudget, GraphNode
from app.knowledge_graph.infrastructure.adjacency import AdjacencyEngine
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository


@dataclass
class LineageNodeInfo:
    node_id: UUID
    node_type: str
    name: str
    source_object_type: str
    source_object_id: UUID


@dataclass
class LineageResult:
    root_node: LineageNodeInfo
    direction: LineageDirection
    lineage_paths: list[dict[str, Any]] = field(default_factory=list)
    nodes: list[LineageNodeInfo] = field(default_factory=list)


class LineageService:
    """Computes forward impact and backward provenance lineages across the graph."""

    def __init__(
        self,
        session: AsyncSession,
        budget: GraphBudget | None = None,
    ) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)
        self.budget = budget or GraphBudget()
        self.adjacency_engine = AdjacencyEngine(self.budget)

    async def get_lineage(
        self,
        node_id: UUID,
        organization_id: UUID,
        direction: LineageDirection = LineageDirection.FORWARD,
        max_depth: int = 4,
    ) -> LineageResult:
        """Trace forward or backward lineage from a target concept or dataset column."""
        root = await self.repo.get_node(node_id, organization_id)
        if not root:
            return LineageResult(
                root_node=LineageNodeInfo(
                    node_id=node_id,
                    node_type="UNKNOWN",
                    name="UNKNOWN",
                    source_object_type="unknown",
                    source_object_id=node_id,
                ),
                direction=direction,
                lineage_paths=[],
                nodes=[],
            )

        edges = await self.repo.list_edges(
            organization_id=organization_id,
            limit=self.budget.max_edges,
        )
        nodes = await self.repo.list_nodes(
            organization_id=organization_id,
            limit=self.budget.max_nodes,
        )
        nodes_by_id: dict[UUID, GraphNode] = {n.id: n for n in nodes}

        # Filter edges by direction
        if direction == LineageDirection.FORWARD:
            # Forward: follow outbound edges
            directional_edges = edges
        else:
            # Reverse: invert source and target for reverse traversal
            directional_edges = [self._reverse_edge(e) for e in edges]

        traversal = self.adjacency_engine.traverse(
            start_node_id=node_id,
            edges=directional_edges,
            nodes_by_id=nodes_by_id,
            max_depth=max_depth,
        )

        lineage_nodes = [
            LineageNodeInfo(
                node_id=n.id,
                node_type=n.node_type.value,
                name=n.name,
                source_object_type=n.source_object_type,
                source_object_id=n.source_object_id,
            )
            for n in traversal.visited_nodes
        ]

        formatted_paths: list[dict[str, Any]] = []
        for e in traversal.visited_edges:
            src = nodes_by_id.get(e.source_node_id)
            tgt = nodes_by_id.get(e.target_node_id)
            formatted_paths.append(
                {
                    "source": src.name if src else str(e.source_node_id),
                    "source_type": src.node_type.value if src else "UNKNOWN",
                    "relationship": e.edge_type.value,
                    "target": tgt.name if tgt else str(e.target_node_id),
                    "target_type": tgt.node_type.value if tgt else "UNKNOWN",
                    "is_verified": e.is_verified,
                }
            )

        return LineageResult(
            root_node=LineageNodeInfo(
                node_id=root.id,
                node_type=root.node_type.value,
                name=root.name,
                source_object_type=root.source_object_type,
                source_object_id=root.source_object_id,
            ),
            direction=direction,
            lineage_paths=formatted_paths,
            nodes=lineage_nodes,
        )

    @staticmethod
    def _reverse_edge(edge: Any) -> Any:
        from dataclasses import replace

        return replace(
            edge,
            source_node_id=edge.target_node_id,
            target_node_id=edge.source_node_id,
        )
