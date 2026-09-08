"""Multi-tenant PostgreSQL repository for Knowledge Graph persistence."""

import uuid
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import (
    ConflictSeverity,
    ConflictStatus,
    GraphEdgeType,
    GraphNodeType,
    GraphStatus,
)
from app.knowledge_graph.domain.errors import (
    CrossTenantGraphViolationError,
    GraphEdgeNotFoundError,
    GraphNodeNotFoundError,
)
from app.knowledge_graph.domain.models import (
    GraphConflict,
    GraphEdge,
    GraphEntityAlias,
    GraphNode,
)
from app.models.knowledge_graph import (
    KnowledgeGraphAlias,
    KnowledgeGraphConflict,
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphVersion,
)


class KnowledgeGraphRepository:
    """Provides transactional and tenant-isolated operations for graph vertices and edges."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -------------------------------------------------------------------------
    # Node Operations
    # -------------------------------------------------------------------------

    async def create_node(
        self,
        organization_id: UUID,
        node_type: GraphNodeType,
        name: str,
        normalized_name: str,
        source_object_type: str,
        source_object_id: UUID,
        metadata: dict[str, Any] | None = None,
        status: GraphStatus = GraphStatus.DRAFT,
    ) -> GraphNode:
        """Create a new vertex in the organization knowledge graph."""
        node_id = uuid.uuid4()
        db_node = KnowledgeGraphNode(
            id=node_id,
            organization_id=organization_id,
            node_type=node_type.value,
            name=name,
            normalized_name=normalized_name,
            source_object_type=source_object_type,
            source_object_id=source_object_id,
            node_metadata=metadata or {},
            status=status.value,
            valid_from=datetime.now(UTC),
            version=1,
        )
        self.session.add(db_node)
        await self.session.flush()
        await self.bump_graph_version(organization_id)
        return self._to_domain_node(db_node)

    async def get_node(self, node_id: UUID, organization_id: UUID) -> GraphNode | None:
        """Retrieve a node ensuring strict tenant isolation."""
        stmt = select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.id == node_id,
            KnowledgeGraphNode.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        db_node = result.scalars().first()
        return self._to_domain_node(db_node) if db_node else None

    async def get_node_by_source(
        self, organization_id: UUID, source_object_type: str, source_object_id: UUID
    ) -> GraphNode | None:
        """Find a node corresponding to an existing underlying database object."""
        stmt = select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.organization_id == organization_id,
            KnowledgeGraphNode.source_object_type == source_object_type,
            KnowledgeGraphNode.source_object_id == source_object_id,
        )
        result = await self.session.execute(stmt)
        db_node = result.scalars().first()
        return self._to_domain_node(db_node) if db_node else None

    async def get_node_by_normalized_name(
        self,
        organization_id: UUID,
        normalized_name: str,
        node_type: GraphNodeType | None = None,
    ) -> GraphNode | None:
        """Find an entity node matching exact normalized string."""
        stmt = select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.organization_id == organization_id,
            KnowledgeGraphNode.normalized_name == normalized_name,
        )
        if node_type:
            stmt = stmt.where(KnowledgeGraphNode.node_type == node_type.value)
        result = await self.session.execute(stmt)
        db_node = result.scalars().first()
        return self._to_domain_node(db_node) if db_node else None

    async def list_nodes(
        self,
        organization_id: UUID,
        node_type: GraphNodeType | None = None,
        status: GraphStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[GraphNode]:
        """List tenant nodes with optional filtering."""
        stmt = select(KnowledgeGraphNode).where(
            KnowledgeGraphNode.organization_id == organization_id
        )
        if node_type:
            stmt = stmt.where(KnowledgeGraphNode.node_type == node_type.value)
        if status:
            stmt = stmt.where(KnowledgeGraphNode.status == status.value)
        stmt = stmt.order_by(KnowledgeGraphNode.name).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return [self._to_domain_node(row) for row in result.scalars().all()]

    async def update_node_status(
        self, node_id: UUID, organization_id: UUID, status: GraphStatus
    ) -> GraphNode:
        """Transition node lifecycle status."""
        stmt = (
            update(KnowledgeGraphNode)
            .where(
                KnowledgeGraphNode.id == node_id,
                KnowledgeGraphNode.organization_id == organization_id,
            )
            .values(status=status.value, updated_at=datetime.now(UTC))
            .returning(KnowledgeGraphNode)
        )
        result = await self.session.execute(stmt)
        db_node = result.scalars().first()
        if not db_node:
            raise GraphNodeNotFoundError(node_id, organization_id)
        await self.bump_graph_version(organization_id)
        return self._to_domain_node(db_node)

    # -------------------------------------------------------------------------
    # Edge Operations
    # -------------------------------------------------------------------------

    async def create_edge(
        self,
        organization_id: UUID,
        source_node_id: UUID,
        target_node_id: UUID,
        edge_type: GraphEdgeType,
        weight: float = 1.0,
        confidence: float = 1.0,
        is_verified: bool = False,
        status: GraphStatus = GraphStatus.DRAFT,
        source_object_type: str | None = None,
        source_object_id: UUID | None = None,
    ) -> GraphEdge:
        """Create a directed edge validating that both endpoints belong to the tenant."""
        # Tenant boundary check on endpoints
        src_node = await self.get_node(source_node_id, organization_id)
        if not src_node:
            raise CrossTenantGraphViolationError(
                f"Source node '{source_node_id}' does not belong to organization.",
                organization_id,
            )
        tgt_node = await self.get_node(target_node_id, organization_id)
        if not tgt_node:
            raise CrossTenantGraphViolationError(
                f"Target node '{target_node_id}' does not belong to organization.",
                organization_id,
            )

        edge_id = uuid.uuid4()
        db_edge = KnowledgeGraphEdge(
            id=edge_id,
            organization_id=organization_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type.value,
            weight=weight,
            confidence=confidence,
            is_verified=is_verified,
            status=status.value,
            source_object_type=source_object_type,
            source_object_id=source_object_id,
            version=1,
            valid_from=datetime.now(UTC),
        )
        self.session.add(db_edge)
        await self.session.flush()
        await self.bump_graph_version(organization_id)
        return self._to_domain_edge(db_edge)

    async def get_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge | None:
        """Retrieve an edge ensuring tenant scope."""
        stmt = select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.id == edge_id,
            KnowledgeGraphEdge.organization_id == organization_id,
        )
        result = await self.session.execute(stmt)
        db_edge = result.scalars().first()
        return self._to_domain_edge(db_edge) if db_edge else None

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
        """Query edges with optional endpoint, type, verification, and status filters."""
        stmt = select(KnowledgeGraphEdge).where(
            KnowledgeGraphEdge.organization_id == organization_id
        )
        if source_node_id:
            stmt = stmt.where(KnowledgeGraphEdge.source_node_id == source_node_id)
        if target_node_id:
            stmt = stmt.where(KnowledgeGraphEdge.target_node_id == target_node_id)
        if edge_type:
            stmt = stmt.where(KnowledgeGraphEdge.edge_type == edge_type.value)
        if only_published:
            stmt = stmt.where(KnowledgeGraphEdge.status == GraphStatus.PUBLISHED.value)
        if only_verified:
            stmt = stmt.where(KnowledgeGraphEdge.is_verified.is_(True))
        stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return [self._to_domain_edge(row) for row in result.scalars().all()]

    async def verify_edge(self, edge_id: UUID, organization_id: UUID) -> GraphEdge:
        """Mark an edge as verified and boost confidence to 1.0."""
        stmt = (
            update(KnowledgeGraphEdge)
            .where(
                KnowledgeGraphEdge.id == edge_id,
                KnowledgeGraphEdge.organization_id == organization_id,
            )
            .values(is_verified=True, confidence=1.0, updated_at=datetime.now(UTC))
            .returning(KnowledgeGraphEdge)
        )
        result = await self.session.execute(stmt)
        db_edge = result.scalars().first()
        if not db_edge:
            raise GraphEdgeNotFoundError(edge_id, organization_id)
        await self.bump_graph_version(organization_id)
        return self._to_domain_edge(db_edge)

    async def update_edge_status(
        self, edge_id: UUID, organization_id: UUID, status: GraphStatus
    ) -> GraphEdge:
        """Update lifecycle status of an edge."""
        stmt = (
            update(KnowledgeGraphEdge)
            .where(
                KnowledgeGraphEdge.id == edge_id,
                KnowledgeGraphEdge.organization_id == organization_id,
            )
            .values(status=status.value, updated_at=datetime.now(UTC))
            .returning(KnowledgeGraphEdge)
        )
        result = await self.session.execute(stmt)
        db_edge = result.scalars().first()
        if not db_edge:
            raise GraphEdgeNotFoundError(edge_id, organization_id)
        await self.bump_graph_version(organization_id)
        return self._to_domain_edge(db_edge)

    # -------------------------------------------------------------------------
    # Alias Operations
    # -------------------------------------------------------------------------

    async def create_alias(
        self,
        organization_id: UUID,
        entity_node_id: UUID,
        alias: str,
        normalized_alias: str,
        language: str = "en",
        source: str = "user",
        is_verified: bool = False,
    ) -> GraphEntityAlias:
        """Map a multilingual synonym or name variant to an entity node."""
        alias_id = uuid.uuid4()
        db_alias = KnowledgeGraphAlias(
            id=alias_id,
            organization_id=organization_id,
            entity_node_id=entity_node_id,
            alias=alias,
            normalized_alias=normalized_alias,
            language=language,
            source=source,
            is_verified=is_verified,
            created_at=datetime.now(UTC),
        )
        self.session.add(db_alias)
        await self.session.flush()
        return self._to_domain_alias(db_alias)

    async def find_aliases_by_normalized_name(
        self, organization_id: UUID, normalized_alias: str
    ) -> list[GraphEntityAlias]:
        """Look up entity aliases matching a normalized string."""
        stmt = select(KnowledgeGraphAlias).where(
            KnowledgeGraphAlias.organization_id == organization_id,
            KnowledgeGraphAlias.normalized_alias == normalized_alias,
        )
        result = await self.session.execute(stmt)
        return [self._to_domain_alias(row) for row in result.scalars().all()]

    async def get_aliases_for_node(
        self, entity_node_id: UUID, organization_id: UUID
    ) -> list[GraphEntityAlias]:
        """Fetch all aliases registered for an entity node."""
        stmt = select(KnowledgeGraphAlias).where(
            KnowledgeGraphAlias.organization_id == organization_id,
            KnowledgeGraphAlias.entity_node_id == entity_node_id,
        )
        result = await self.session.execute(stmt)
        return [self._to_domain_alias(row) for row in result.scalars().all()]

    # -------------------------------------------------------------------------
    # Conflict Operations
    # -------------------------------------------------------------------------

    async def create_conflict(
        self,
        organization_id: UUID,
        reason: str,
        severity: ConflictSeverity = ConflictSeverity.MEDIUM,
        node_ids: list[UUID] | None = None,
        edge_ids: list[UUID] | None = None,
    ) -> GraphConflict:
        """Record a discovered structural collision or contradictory path."""
        conflict_id = uuid.uuid4()
        db_conflict = KnowledgeGraphConflict(
            id=conflict_id,
            organization_id=organization_id,
            reason=reason,
            severity=severity.value,
            node_ids=[str(nid) for nid in (node_ids or [])],
            edge_ids=[str(eid) for eid in (edge_ids or [])],
            status=ConflictStatus.OPEN.value,
            created_at=datetime.now(UTC),
        )
        self.session.add(db_conflict)
        await self.session.flush()
        return self._to_domain_conflict(db_conflict)

    async def list_conflicts(
        self,
        organization_id: UUID,
        status: ConflictStatus | None = None,
    ) -> list[GraphConflict]:
        """List active or resolved graph conflicts."""
        stmt = select(KnowledgeGraphConflict).where(
            KnowledgeGraphConflict.organization_id == organization_id
        )
        if status:
            stmt = stmt.where(KnowledgeGraphConflict.status == status.value)
        stmt = stmt.order_by(desc(KnowledgeGraphConflict.created_at))
        result = await self.session.execute(stmt)
        return [self._to_domain_conflict(row) for row in result.scalars().all()]

    # -------------------------------------------------------------------------
    # Versioning & Cache Invalidation
    # -------------------------------------------------------------------------

    async def get_graph_version(self, organization_id: UUID) -> int:
        """Fetch the current version number for tenant graph state."""
        stmt = select(KnowledgeGraphVersion).where(
            KnowledgeGraphVersion.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        v = result.scalars().first()
        if not v:
            # Initialize version to 1
            init_v = KnowledgeGraphVersion(
                id=uuid.uuid4(),
                organization_id=organization_id,
                version=1,
                updated_at=datetime.now(UTC),
            )
            self.session.add(init_v)
            await self.session.flush()
            return 1
        return v.version

    async def bump_graph_version(self, organization_id: UUID) -> int:
        """Increment tenant graph version to invalidate caches and record provenance."""
        stmt = select(KnowledgeGraphVersion).where(
            KnowledgeGraphVersion.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        v = result.scalars().first()
        if not v:
            v = KnowledgeGraphVersion(
                id=uuid.uuid4(),
                organization_id=organization_id,
                version=2,
                updated_at=datetime.now(UTC),
            )
            self.session.add(v)
            await self.session.flush()
            return 2
        v.version += 1
        v.updated_at = datetime.now(UTC)
        await self.session.flush()
        return v.version

    # -------------------------------------------------------------------------
    # Domain Object Mappers
    # -------------------------------------------------------------------------

    @staticmethod
    def _to_domain_node(model: KnowledgeGraphNode) -> GraphNode:
        return GraphNode(
            id=model.id,
            organization_id=model.organization_id,
            node_type=GraphNodeType(model.node_type),
            name=model.name,
            normalized_name=model.normalized_name,
            source_object_type=model.source_object_type,
            source_object_id=model.source_object_id,
            version=model.version,
            metadata=model.node_metadata or {},
            status=GraphStatus(model.status),
            valid_from=model.valid_from,
            valid_to=model.valid_to,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_domain_edge(model: KnowledgeGraphEdge) -> GraphEdge:
        return GraphEdge(
            id=model.id,
            organization_id=model.organization_id,
            source_node_id=model.source_node_id,
            target_node_id=model.target_node_id,
            edge_type=GraphEdgeType(model.edge_type),
            weight=model.weight,
            confidence=model.confidence,
            is_verified=model.is_verified,
            status=GraphStatus(model.status),
            source_object_type=model.source_object_type,
            source_object_id=model.source_object_id,
            version=model.version,
            valid_from=model.valid_from,
            valid_to=model.valid_to,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_domain_alias(model: KnowledgeGraphAlias) -> GraphEntityAlias:
        return GraphEntityAlias(
            id=model.id,
            organization_id=model.organization_id,
            entity_node_id=model.entity_node_id,
            alias=model.alias,
            normalized_alias=model.normalized_alias,
            language=model.language,
            source=model.source,
            is_verified=model.is_verified,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_domain_conflict(model: KnowledgeGraphConflict) -> GraphConflict:
        return GraphConflict(
            id=model.id,
            organization_id=model.organization_id,
            reason=model.reason,
            severity=ConflictSeverity(model.severity),
            node_ids=[uuid.UUID(nid) for nid in (model.node_ids or [])],
            edge_ids=[uuid.UUID(eid) for eid in (model.edge_ids or [])],
            status=ConflictStatus(model.status),
            created_at=model.created_at,
            resolved_at=model.resolved_at,
            resolved_by=model.resolved_by,
        )
