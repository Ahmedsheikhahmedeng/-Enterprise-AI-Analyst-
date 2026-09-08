"""Application service managing knowledge graph relationships and verification."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import (
    GraphEdgeType,
    GraphStatus,
    RelationshipConfidenceTier,
)
from app.knowledge_graph.domain.errors import (
    GraphEdgeNotFoundError,
    GraphPublishingError,
)
from app.knowledge_graph.domain.models import GraphEdge
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository


class EdgeService:
    """Provides validated edge creation, tenant boundary enforcement, and verification."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)

    async def create_edge(
        self,
        organization_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: GraphEdgeType,
        weight: float = 1.0,
        confidence: float | None = None,
        is_verified: bool = False,
        status: GraphStatus = GraphStatus.DRAFT,
        source_object_type: str | None = None,
        source_object_id: UUID | None = None,
    ) -> GraphEdge:
        """Create a directed relationship enforcing tenant boundary on endpoints."""
        effective_confidence = (
            confidence
            if confidence is not None
            else (
                RelationshipConfidenceTier.VERIFIED.value
                if is_verified
                else RelationshipConfidenceTier.INFERRED.value
            )
        )
        return await self.repo.create_edge(
            organization_id=organization_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            weight=weight,
            confidence=effective_confidence,
            is_verified=is_verified,
            status=status,
            source_object_type=source_object_type,
            source_object_id=source_object_id,
        )

    async def get_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        """Fetch edge ensuring tenant scope."""
        edge = await self.repo.get_edge(edge_id, organization_id)
        if not edge:
            raise GraphEdgeNotFoundError(edge_id, organization_id)
        return edge

    async def list_edges(
        self,
        organization_id: UUID,
        source_node_id: UUID | None = None,
        target_node_id: UUID | None = None,
        edge_type: GraphEdgeType | None = None,
        only_published: bool = False,
        only_verified: bool = False,
        limit: int = 1000,
    ) -> list[GraphEdge]:
        """List tenant edges."""
        return await self.repo.list_edges(
            organization_id=organization_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            only_published=only_published,
            only_verified=only_verified,
            limit=limit,
        )

    async def verify_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        """Verify an edge, setting is_verified=True and confidence=1.0."""
        await self.get_edge(edge_id, organization_id)
        return await self.repo.verify_edge(edge_id, organization_id)

    async def publish_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        """Transition edge to PUBLISHED state."""
        edge = await self.get_edge(edge_id, organization_id)
        if edge.status == GraphStatus.ARCHIVED:
            raise GraphPublishingError(edge_id, edge.status.value)
        return await self.repo.update_edge_status(
            edge_id=edge_id,
            organization_id=organization_id,
            status=GraphStatus.PUBLISHED,
        )

    async def archive_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        """Transition edge to ARCHIVED state."""
        return await self.repo.update_edge_status(
            edge_id=edge_id,
            organization_id=organization_id,
            status=GraphStatus.ARCHIVED,
        )
