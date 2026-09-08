"""Compiles natural language questions into structured Knowledge Graph reasoning plans."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.application.entity_resolution_service import (
    EntityResolutionService,
)
from app.knowledge_graph.application.path_service import PathService
from app.knowledge_graph.domain.enums import GraphNodeType, ResolutionStatus
from app.knowledge_graph.domain.models import (
    GraphPath,
    GraphProvenance,
    GraphQueryResult,
)
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.semantic.infrastructure.search import HybridSemanticSearchEngine


class GraphQueryPlanner:
    """Decomposes natural language queries into entities and multi-hop relationship paths."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)
        self.entity_resolver = EntityResolutionService(session)
        self.path_service = PathService(session)
        self.search_engine = HybridSemanticSearchEngine(session)

    async def plan_graph_reasoning(
        self,
        question: str,
        organization_id: UUID,
        max_depth: int = 3,
    ) -> GraphQueryResult:
        """Analyze question concepts, discover connecting graph paths, and construct join plan."""
        graph_version = await self.repo.get_graph_version(organization_id)

        # 1. Semantic Discovery for candidate metrics, dimensions, and terms
        search_hits = await self.search_engine.search(
            query=question,
            organization_id=organization_id,
            limit=5,
            only_published=True,
        )

        # 2. Extract and resolve candidate entity tokens
        # Split tokens and check with entity resolver
        tokens = question.replace("?", " ").replace("؟", " ").replace(",", " ").split()
        resolved_entity_nodes = []
        visited_entity_ids = set()

        for token in tokens:
            if len(token) >= 3:
                res = await self.entity_resolver.resolve(token, organization_id)
                if (
                    res.status == ResolutionStatus.RESOLVED
                    and res.entity_node_id
                    and res.entity_node_id not in visited_entity_ids
                ):
                    node = await self.repo.get_node(res.entity_node_id, organization_id)
                    if node:
                        resolved_entity_nodes.append(node)
                        visited_entity_ids.add(node.id)

        # 3. Locate target concept nodes from search hits
        target_concept_nodes = []
        for hit in search_hits:
            node = await self.repo.get_node_by_source(
                organization_id, hit.object_type.value, hit.object_id
            )
            if node and node.id not in visited_entity_ids:
                target_concept_nodes.append(node)

        # 4. Search connecting paths between identified entities and target concepts
        discovered_paths: list[GraphPath] = []
        node_ids_used: set[UUID] = set()
        edge_ids_used: set[UUID] = set()
        source_object_ids_used: set[UUID] = set()

        for ent_node in resolved_entity_nodes:
            for tgt_node in target_concept_nodes:
                paths = await self.path_service.find_paths(
                    start_node_id=ent_node.id,
                    target_node_id=tgt_node.id,
                    organization_id=organization_id,
                    max_depth=max_depth,
                    only_published=True,
                )
                for p in paths:
                    discovered_paths.append(p)
                    for n in p.nodes:
                        node_ids_used.add(n.id)
                        source_object_ids_used.add(n.source_object_id)
                    for e in p.edges:
                        edge_ids_used.add(e.id)

        discovered_paths.sort(key=lambda p: (-p.confidence, p.depth))
        top_conf = discovered_paths[0].confidence if discovered_paths else 0.0
        is_verified = bool(discovered_paths and discovered_paths[0].verified_ratio == 1.0)

        provenance = GraphProvenance(
            organization_id=organization_id,
            graph_version=graph_version,
            node_ids=list(node_ids_used),
            edge_ids=list(edge_ids_used),
            source_object_ids=list(source_object_ids_used),
            verified_status=is_verified,
            confidence=top_conf,
        )

        return GraphQueryResult(
            paths=discovered_paths,
            confidence=top_conf,
            provenance=provenance,
            resolved_entities=[
                {"id": str(n.id), "name": n.name, "type": n.node_type.value}
                for n in resolved_entity_nodes
            ],
            resolved_metrics=[
                {"id": str(n.id), "name": n.name}
                for n in target_concept_nodes
                if n.node_type == GraphNodeType.METRIC
            ],
            resolved_dimensions=[
                {"id": str(n.id), "name": n.name}
                for n in target_concept_nodes
                if n.node_type == GraphNodeType.DIMENSION
            ],
        )
