"""High-level Knowledge Graph application facade service."""

from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.application.conflict_detector import GraphConflictDetector
from app.knowledge_graph.application.edge_service import EdgeService
from app.knowledge_graph.application.graph_query_service import GraphQueryService
from app.knowledge_graph.application.graph_sync_service import (
    GraphSyncService,
    GraphSyncSummary,
)
from app.knowledge_graph.application.node_service import NodeService
from app.knowledge_graph.application.path_service import PathService
from app.knowledge_graph.application.traversal_service import TraversalService
from app.knowledge_graph.domain.enums import (
    GraphEdgeType,
    GraphStatus,
)
from app.knowledge_graph.domain.models import (
    GraphConflict,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphQuery,
    GraphQueryResult,
    GraphTraversal,
)
from app.knowledge_graph.infrastructure.cache import KnowledgeGraphCache
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository


class KnowledgeGraphService:
    """Unified entrypoint coordinating all knowledge graph domain operations."""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Redis | None = None,
        repo: KnowledgeGraphRepository | None = None,
    ) -> None:
        self.session = session
        self.repo = repo or KnowledgeGraphRepository(session)
        self.node_service = NodeService(session)
        self.edge_service = EdgeService(session)
        self.traversal_service = TraversalService(session)
        self.path_service = PathService(session, repo=self.repo)
        self.sync_service = GraphSyncService(session)
        self.conflict_detector = GraphConflictDetector(session)
        self.query_service = GraphQueryService(session, redis_client=redis_client)
        self.cache = KnowledgeGraphCache(redis_client)

    async def sync_catalog(self, organization_id: UUID) -> GraphSyncSummary:
        """Synchronize semantic models into the knowledge graph and invalidate cache."""
        summary = await self.sync_service.sync_organization_graph(organization_id)
        await self.cache.invalidate_tenant(organization_id)
        return summary

    async def query(self, query: GraphQuery, organization_id: UUID) -> GraphQueryResult:
        """Execute structured graph reasoning query."""
        return await self.query_service.execute_query(query, organization_id)

    async def get_node(self, node_id: UUID, organization_id: UUID) -> GraphNode:
        return await self.node_service.get_node(node_id, organization_id)

    async def get_neighbors(
        self,
        node_id: UUID,
        organization_id: UUID,
        depth: int = 1,
        edge_types: list[GraphEdgeType] | None = None,
        only_published: bool = True,
    ) -> GraphTraversal:
        return await self.traversal_service.get_neighbors(
            node_id=node_id,
            organization_id=organization_id,
            depth=depth,
            edge_types=edge_types,
            only_published=only_published,
        )

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
        return await self.path_service.find_paths(
            start_node_id=start_node_id,
            target_node_id=target_node_id,
            organization_id=organization_id,
            max_depth=max_depth,
            max_paths=max_paths,
            edge_types=edge_types,
            only_published=only_published,
            only_verified=only_verified,
        )

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
    ) -> GraphEdge:
        edge = await self.edge_service.create_edge(
            organization_id=organization_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            weight=weight,
            confidence=confidence,
            is_verified=is_verified,
            status=status,
        )
        await self.cache.invalidate_tenant(organization_id)
        return edge

    async def verify_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        edge = await self.edge_service.verify_edge(edge_id, organization_id)
        await self.cache.invalidate_tenant(organization_id)
        return edge

    async def publish_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        edge = await self.edge_service.publish_edge(edge_id, organization_id)
        await self.cache.invalidate_tenant(organization_id)
        return edge

    async def publish_node(self, node_id: UUID, organization_id: UUID) -> GraphNode:
        node = await self.node_service.publish_node(node_id, organization_id)
        await self.cache.invalidate_tenant(organization_id)
        return node

    async def detect_conflicts(self, organization_id: UUID) -> list[GraphConflict]:
        return await self.conflict_detector.detect_conflicts(organization_id)

    async def list_conflicts(self, organization_id: UUID) -> list[GraphConflict]:
        return await self.repo.list_conflicts(organization_id)
