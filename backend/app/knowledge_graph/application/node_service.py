"""Application service managing knowledge graph vertices and their lifecycle states."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import GraphNodeType, GraphStatus
from app.knowledge_graph.domain.errors import (
    GraphNodeNotFoundError,
    GraphPublishingError,
)
from app.knowledge_graph.domain.models import GraphNode
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.semantic.application.normalizer import SemanticTextNormalizer


class NodeService:
    """Provides validated node creation, discovery, and publishing lifecycle transitions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)

    async def create_node(
        self,
        organization_id: UUID,
        node_type: GraphNodeType,
        name: str,
        source_object_type: str,
        source_object_id: UUID,
        metadata: dict[str, Any] | None = None,
        status: GraphStatus = GraphStatus.DRAFT,
    ) -> GraphNode:
        """Create and index a new graph node."""
        normalized_name = SemanticTextNormalizer.normalize(name)
        return await self.repo.create_node(
            organization_id=organization_id,
            node_type=node_type,
            name=name,
            normalized_name=normalized_name,
            source_object_type=source_object_type,
            source_object_id=source_object_id,
            metadata=metadata,
            status=status,
        )

    async def get_node(self, node_id: UUID, organization_id: UUID) -> GraphNode:
        """Fetch node ensuring tenant scoping."""
        node = await self.repo.get_node(node_id, organization_id)
        if not node:
            raise GraphNodeNotFoundError(node_id, organization_id)
        return node

    async def list_nodes(
        self,
        organization_id: UUID,
        node_type: GraphNodeType | None = None,
        status: GraphStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GraphNode]:
        """List tenant nodes."""
        return await self.repo.list_nodes(
            organization_id=organization_id,
            node_type=node_type,
            status=status,
            limit=limit,
            offset=offset,
        )

    async def publish_node(self, node_id: UUID, organization_id: UUID) -> GraphNode:
        """Transition node to PUBLISHED status for production reasoning."""
        node = await self.get_node(node_id, organization_id)
        if node.status == GraphStatus.ARCHIVED:
            raise GraphPublishingError(node_id, node.status.value)
        return await self.repo.update_node_status(
            node_id=node_id,
            organization_id=organization_id,
            status=GraphStatus.PUBLISHED,
        )

    async def archive_node(self, node_id: UUID, organization_id: UUID) -> GraphNode:
        """Transition node to ARCHIVED status."""
        return await self.repo.update_node_status(
            node_id=node_id,
            organization_id=organization_id,
            status=GraphStatus.ARCHIVED,
        )
