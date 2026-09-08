"""Coordinates graph querying, path resolution, provenance assembly, and Redis caching."""

import time
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.application.entity_resolution_service import (
    EntityResolutionService,
)
from app.knowledge_graph.application.path_service import PathService
from app.knowledge_graph.domain.enums import ResolutionStatus
from app.knowledge_graph.domain.models import (
    GraphProvenance,
    GraphQuery,
    GraphQueryResult,
)
from app.knowledge_graph.infrastructure.cache import KnowledgeGraphCache
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.observability.instrumentation.knowledge_graph import (
    get_knowledge_graph_instrumentation,
)


class GraphQueryService:
    """Executes structured graph reasoning queries with caching and complete provenance."""

    def __init__(
        self,
        session: AsyncSession,
        redis_client: Redis | None = None,
    ) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)
        self.path_service = PathService(session)
        self.entity_resolver = EntityResolutionService(session)
        self.cache = KnowledgeGraphCache(redis_client)
        self.instrumentation = get_knowledge_graph_instrumentation()

    async def execute_query(
        self,
        query: GraphQuery,
        organization_id: UUID,
    ) -> GraphQueryResult:
        """Execute a graph traversal query between resolved concepts."""
        t_start = time.perf_counter()
        graph_version = await self.repo.get_graph_version(organization_id)

        # 1. Resolve start node ID(s)
        start_ids: list[UUID] = query.start_node_ids or []
        resolved_entities_meta: list[dict[str, Any]] = []

        if not start_ids and query.start_entity:
            res = await self.entity_resolver.resolve(query.start_entity, organization_id)
            if res.status == ResolutionStatus.RESOLVED and res.entity_node_id:
                start_ids.append(res.entity_node_id)
                resolved_entities_meta.append(
                    {
                        "name": res.entity_name,
                        "id": str(res.entity_node_id),
                        "confidence": res.confidence,
                    }
                )

        # 2. Resolve target node ID(s)
        target_ids: list[UUID] = query.target_node_ids or []
        if not target_ids and query.target_concept:
            # Try finding target node by normalized name
            norm_tgt = query.target_concept.strip().lower()
            node = await self.repo.get_node_by_normalized_name(organization_id, norm_tgt)
            if node:
                target_ids.append(node.id)
            else:
                # Try entity resolution
                res_tgt = await self.entity_resolver.resolve(query.target_concept, organization_id)
                if res_tgt.status == ResolutionStatus.RESOLVED and res_tgt.entity_node_id:
                    target_ids.append(res_tgt.entity_node_id)

        all_paths = []
        node_ids_used: set[UUID] = set()
        edge_ids_used: set[UUID] = set()
        source_object_ids_used: set[UUID] = set()

        for s_id in start_ids:
            for t_id in target_ids:
                paths = await self.path_service.find_paths(
                    start_node_id=s_id,
                    target_node_id=t_id,
                    organization_id=organization_id,
                    max_depth=query.max_depth,
                    edge_types=query.edge_types,
                    only_published=query.only_published,
                    only_verified=query.only_verified,
                )
                for p in paths:
                    if p.confidence >= query.min_confidence:
                        all_paths.append(p)
                        for n in p.nodes:
                            node_ids_used.add(n.id)
                            source_object_ids_used.add(n.source_object_id)
                        for e in p.edges:
                            edge_ids_used.add(e.id)

        # Sort combined paths by confidence descending
        all_paths.sort(key=lambda p: (-p.confidence, p.depth))
        top_confidence = all_paths[0].confidence if all_paths else 0.0
        is_all_verified = bool(all_paths and all_paths[0].verified_ratio == 1.0)

        provenance = GraphProvenance(
            organization_id=organization_id,
            graph_version=graph_version,
            node_ids=list(node_ids_used),
            edge_ids=list(edge_ids_used),
            source_object_ids=list(source_object_ids_used),
            verified_status=is_all_verified,
            confidence=top_confidence,
        )

        duration = time.perf_counter() - t_start
        self.instrumentation.record_query(
            graph_operation="find_paths" if target_ids else "traverse",
            status="success" if all_paths else "empty",
            duration_s=duration,
        )

        return GraphQueryResult(
            paths=all_paths,
            confidence=top_confidence,
            provenance=provenance,
            resolved_entities=resolved_entities_meta,
            resolved_metrics=[],
            resolved_dimensions=[],
        )
