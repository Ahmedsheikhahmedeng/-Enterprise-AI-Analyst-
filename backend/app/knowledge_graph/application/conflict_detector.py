"""Conflict and cycle detection for knowledge graph relationships and join paths."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import (
    ConflictSeverity,
    GraphEdgeType,
)
from app.knowledge_graph.domain.models import GraphConflict, GraphEdge
from app.knowledge_graph.infrastructure.adjacency import AdjacencyEngine
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.observability.instrumentation.knowledge_graph import (
    get_knowledge_graph_instrumentation,
)

logger = logging.getLogger(__name__)


class GraphConflictDetector:
    """Discovers structural collisions, competing joins, and cycles in the graph."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)
        self.instrumentation = get_knowledge_graph_instrumentation()

    async def detect_conflicts(self, organization_id: UUID) -> list[GraphConflict]:
        """Scan active relationships for contradictory join definitions or primary collisions."""
        edges = await self.repo.list_edges(organization_id=organization_id, limit=2000)
        conflicts: list[GraphConflict] = []

        # 1. Check for multiple distinct JOINS_WITH between same source entity and different targets
        # where both are marked as primary / verified
        join_edges = [
            e for e in edges if e.edge_type in (GraphEdgeType.JOINS_WITH, GraphEdgeType.RELATES_TO)
        ]
        source_targets: dict[UUID, list[GraphEdge]] = {}
        for edge in join_edges:
            source_targets.setdefault(edge.source_node_id, []).append(edge)

        for src_id, edge_list in source_targets.items():
            verified_edges = [e for e in edge_list if e.is_verified]
            # If an entity has multiple competing primary join edges to different entities
            target_ids = {e.target_node_id for e in verified_edges}
            if len(target_ids) > 2:
                reason = (
                    f"Entity node '{src_id}' has {len(target_ids)} distinct verified join targets. "
                    "Possible join ambiguity or conflicting primary transactional relationship."
                )
                conflict = await self.repo.create_conflict(
                    organization_id=organization_id,
                    reason=reason,
                    severity=ConflictSeverity.MEDIUM,
                    node_ids=[src_id] + list(target_ids),
                    edge_ids=[e.id for e in verified_edges],
                )
                conflicts.append(conflict)
                self.instrumentation.record_conflict(status="OPEN")

        # 2. Cycle Detection
        cycles = AdjacencyEngine.detect_cycles(edges)
        for cycle in cycles:
            reason = (
                f"Circular relationship detected among nodes: {' -> '.join(str(n) for n in cycle)}"
            )
            conflict = await self.repo.create_conflict(
                organization_id=organization_id,
                reason=reason,
                severity=ConflictSeverity.LOW,  # Cycles are flagged, not fatal
                node_ids=cycle,
                edge_ids=[],
            )
            conflicts.append(conflict)
            self.instrumentation.record_conflict(status="OPEN")

        return conflicts
