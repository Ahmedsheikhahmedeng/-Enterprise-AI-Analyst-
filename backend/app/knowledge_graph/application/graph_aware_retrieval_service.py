"""Graph-Aware Retrieval expanding search queries using 1-2 hop neighborhood context."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.application.entity_resolution_service import (
    EntityResolutionService,
)
from app.knowledge_graph.application.traversal_service import TraversalService
from app.knowledge_graph.domain.enums import ResolutionStatus


@dataclass
class GraphExpansionResult:
    """Expanded query concepts and terms retrieved from knowledge graph neighborhood."""

    original_query: str
    expanded_terms: list[str] = field(default_factory=list)
    confidence: float = 0.0
    source_type: str = "graph_catalog"
    related_node_names: list[str] = field(default_factory=list)


class GraphAwareRetrievalService:
    """Expands document retrieval queries using high-confidence 1-2 hop graph neighborhoods."""

    def __init__(
        self,
        session: AsyncSession,
        confidence_threshold: float = 0.70,
    ) -> None:
        self.session = session
        self.confidence_threshold = confidence_threshold
        self.entity_resolver = EntityResolutionService(session)
        self.traversal_service = TraversalService(session)

    async def expand_query(
        self,
        query: str,
        organization_id: UUID,
        max_depth: int = 2,
    ) -> GraphExpansionResult:
        """Resolve query concepts and expand with 1-2 hop neighbors if confidence >= threshold."""
        # 1. Check if an entity can be resolved
        res = await self.entity_resolver.resolve(query, organization_id)
        if (
            res.status != ResolutionStatus.RESOLVED
            or not res.entity_node_id
            or res.confidence < self.confidence_threshold
        ):
            return GraphExpansionResult(
                original_query=query,
                expanded_terms=[],
                confidence=res.confidence,
                related_node_names=[],
            )

        # 2. Perform bounded 1-2 hop neighborhood expansion
        traversal = await self.traversal_service.get_neighbors(
            node_id=res.entity_node_id,
            organization_id=organization_id,
            depth=min(max_depth, 2),
            only_published=True,
        )

        expanded_terms: list[str] = []
        related_names: list[str] = []

        for node in traversal.visited_nodes:
            if node.id != res.entity_node_id:
                related_names.append(node.name)
                # Add aliases or tokens
                expanded_terms.append(node.name)

        return GraphExpansionResult(
            original_query=query,
            expanded_terms=list(set(expanded_terms)),
            confidence=res.confidence,
            source_type="graph_catalog",
            related_node_names=related_names,
        )
