"""FastAPI REST API routes for Knowledge Graph and Relationship Reasoning."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestAppException, NotFoundAppException
from app.db.postgres import get_db_session
from app.knowledge_graph.api.schemas import (
    GraphConflictResponse,
    GraphEdgeCreateRequest,
    GraphEdgeResponse,
    GraphEdgeUpdateRequest,
    GraphLineageResponse,
    GraphNeighborsResponse,
    GraphNodeResponse,
    GraphPathItemResponse,
    GraphPathsRequest,
    GraphPathsResponse,
    GraphQueryRequest,
    GraphQueryResponse,
    GraphSearchRequest,
    GraphSearchResponse,
    GraphSyncResponse,
)
from app.knowledge_graph.application.graph_service import KnowledgeGraphService
from app.knowledge_graph.application.lineage_service import LineageService
from app.knowledge_graph.domain.enums import (
    GraphEdgeType,
    GraphNodeType,
    GraphStatus,
    LineageDirection,
)
from app.knowledge_graph.domain.errors import (
    GraphEdgeNotFoundError,
    GraphNodeNotFoundError,
    KnowledgeGraphError,
)
from app.knowledge_graph.domain.models import GraphQuery
from app.rbac.catalog import (
    PERM_GRAPH_CREATE,
    PERM_GRAPH_PUBLISH,
    PERM_GRAPH_READ,
    PERM_GRAPH_TRAVERSE,
    PERM_GRAPH_UPDATE,
)
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/graph", tags=["Knowledge Graph & Relationship Reasoning"])


@router.post(
    "/search",
    response_model=GraphSearchResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_READ))],
)
async def search_graph_nodes(
    payload: GraphSearchRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphSearchResponse:
    """Search registered vertices in the knowledge graph."""
    service = KnowledgeGraphService(db_session)
    type_filter = GraphNodeType(payload.node_type) if payload.node_type else None
    nodes = await service.node_service.list_nodes(
        organization_id=tenant_context.organization_id,
        node_type=type_filter,
        limit=payload.limit,
    )
    q_lower = payload.query.lower()
    matched = [n for n in nodes if q_lower in n.name.lower() or q_lower in n.normalized_name]
    items = [
        GraphNodeResponse(
            id=n.id,
            organization_id=n.organization_id,
            node_type=n.node_type.value,
            name=n.name,
            normalized_name=n.normalized_name,
            source_object_type=n.source_object_type,
            source_object_id=n.source_object_id,
            version=n.version,
            metadata=n.metadata,
            status=n.status.value,
            valid_from=n.valid_from,
            valid_to=n.valid_to,
        )
        for n in matched
    ]
    return GraphSearchResponse(nodes=items, count=len(items))


@router.get(
    "/nodes/{node_id}",
    response_model=GraphNodeResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_READ))],
)
async def get_graph_node(
    node_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphNodeResponse:
    """Retrieve full details for a knowledge graph vertex."""
    service = KnowledgeGraphService(db_session)
    try:
        node = await service.get_node(node_id, tenant_context.organization_id)
        return GraphNodeResponse(
            id=node.id,
            organization_id=node.organization_id,
            node_type=node.node_type.value,
            name=node.name,
            normalized_name=node.normalized_name,
            source_object_type=node.source_object_type,
            source_object_id=node.source_object_id,
            version=node.version,
            metadata=node.metadata,
            status=node.status.value,
            valid_from=node.valid_from,
            valid_to=node.valid_to,
        )
    except GraphNodeNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc


@router.get(
    "/nodes/{node_id}/neighbors",
    response_model=GraphNeighborsResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_TRAVERSE))],
)
async def get_node_neighbors(
    node_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    depth: int = Query(default=1, ge=1, le=4),
) -> GraphNeighborsResponse:
    """Retrieve 1-4 hop neighbors and relationships around a vertex."""
    service = KnowledgeGraphService(db_session)
    traversal = await service.get_neighbors(
        node_id=node_id,
        organization_id=tenant_context.organization_id,
        depth=depth,
        only_published=True,
    )
    nodes_res = [
        GraphNodeResponse(
            id=n.id,
            organization_id=n.organization_id,
            node_type=n.node_type.value,
            name=n.name,
            normalized_name=n.normalized_name,
            source_object_type=n.source_object_type,
            source_object_id=n.source_object_id,
            version=n.version,
            metadata=n.metadata,
            status=n.status.value,
            valid_from=n.valid_from,
            valid_to=n.valid_to,
        )
        for n in traversal.visited_nodes
    ]
    edges_res = [
        GraphEdgeResponse(
            id=e.id,
            organization_id=e.organization_id,
            source_node_id=e.source_node_id,
            target_node_id=e.target_node_id,
            edge_type=e.edge_type.value,
            weight=e.weight,
            confidence=e.confidence,
            is_verified=e.is_verified,
            status=e.status.value,
            source_object_type=e.source_object_type,
            source_object_id=e.source_object_id,
            version=e.version,
        )
        for e in traversal.visited_edges
    ]
    return GraphNeighborsResponse(
        root_node_id=node_id,
        depth=traversal.depth,
        nodes=nodes_res,
        edges=edges_res,
    )


@router.post(
    "/paths",
    response_model=GraphPathsResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_TRAVERSE))],
)
async def find_graph_paths(
    payload: GraphPathsRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphPathsResponse:
    """Find ranked multi-hop relationship paths between two vertices."""
    service = KnowledgeGraphService(db_session)
    paths = await service.find_paths(
        start_node_id=payload.start_node_id,
        target_node_id=payload.target_node_id,
        organization_id=tenant_context.organization_id,
        max_depth=payload.max_depth,
        max_paths=payload.max_paths,
        only_published=True,
        only_verified=payload.only_verified,
    )
    items = [
        GraphPathItemResponse(
            depth=p.depth,
            confidence=p.confidence,
            verified_ratio=p.verified_ratio,
            nodes=[n.name for n in p.nodes],
            edges=[e.edge_type.value for e in p.edges],
        )
        for p in paths
    ]
    return GraphPathsResponse(paths=items, count=len(items))


@router.post(
    "/query",
    response_model=GraphQueryResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_TRAVERSE))],
)
async def query_graph_reasoning(
    payload: GraphQueryRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphQueryResponse:
    """Execute concept-to-concept relationship resolution across the graph."""
    service = KnowledgeGraphService(db_session)
    q = GraphQuery(
        start_entity=payload.start_entity,
        target_concept=payload.target_concept,
        max_depth=payload.max_depth,
        only_published=True,
    )
    result = await service.query(q, tenant_context.organization_id)
    items = [
        GraphPathItemResponse(
            depth=p.depth,
            confidence=p.confidence,
            verified_ratio=p.verified_ratio,
            nodes=[n.name for n in p.nodes],
            edges=[e.edge_type.value for e in p.edges],
        )
        for p in result.paths
    ]
    provenance_data = {
        "graph_version": result.provenance.graph_version,
        "verified_status": result.provenance.verified_status,
        "nodes_used_count": len(result.provenance.node_ids),
        "edges_used_count": len(result.provenance.edge_ids),
    }
    return GraphQueryResponse(
        confidence=result.confidence,
        paths=items,
        provenance=provenance_data,
        resolved_entities=result.resolved_entities,
    )


@router.get(
    "/nodes/{node_id}/lineage",
    response_model=GraphLineageResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_READ))],
)
async def get_node_lineage(
    node_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    direction: str = Query(default="FORWARD", pattern="^(FORWARD|REVERSE)$"),
    max_depth: int = Query(default=4, ge=1, le=4),
) -> GraphLineageResponse:
    """Trace forward or backward semantic lineage from a target vertex."""
    lineage_service = LineageService(db_session)
    dir_enum = (
        LineageDirection.REVERSE if direction.upper() == "REVERSE" else LineageDirection.FORWARD
    )
    res = await lineage_service.get_lineage(
        node_id=node_id,
        organization_id=tenant_context.organization_id,
        direction=dir_enum,
        max_depth=max_depth,
    )
    return GraphLineageResponse(
        root_node_id=res.root_node.node_id,
        direction=res.direction.value,
        lineage_paths=res.lineage_paths,
        nodes_count=len(res.nodes),
    )


@router.get(
    "/conflicts",
    response_model=list[GraphConflictResponse],
    dependencies=[Depends(require_permission(PERM_GRAPH_READ))],
)
async def list_graph_conflicts(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[GraphConflictResponse]:
    """List structural collisions or conflicting join paths detected in the graph."""
    service = KnowledgeGraphService(db_session)
    conflicts = await service.list_conflicts(tenant_context.organization_id)
    return [
        GraphConflictResponse(
            id=c.id,
            reason=c.reason,
            severity=c.severity.value,
            node_ids=[str(nid) for nid in c.node_ids],
            edge_ids=[str(eid) for eid in c.edge_ids],
            status=c.status.value,
            created_at=c.created_at,
        )
        for c in conflicts
    ]


@router.post(
    "/edges",
    response_model=GraphEdgeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_GRAPH_CREATE))],
)
async def create_graph_edge(
    payload: GraphEdgeCreateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphEdgeResponse:
    """Create a new relationship edge between two tenant vertices."""
    service = KnowledgeGraphService(db_session)
    try:
        edge_type = GraphEdgeType(payload.edge_type)
    except ValueError as exc:
        raise BadRequestAppException(f"Invalid edge_type: {payload.edge_type}") from exc

    try:
        edge = await service.create_edge(
            organization_id=tenant_context.organization_id,
            source_node_id=payload.source_node_id,
            target_node_id=payload.target_node_id,
            edge_type=edge_type,
            weight=payload.weight,
            confidence=payload.confidence,
            is_verified=payload.is_verified,
        )
        return GraphEdgeResponse(
            id=edge.id,
            organization_id=edge.organization_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            edge_type=edge.edge_type.value,
            weight=edge.weight,
            confidence=edge.confidence,
            is_verified=edge.is_verified,
            status=edge.status.value,
            source_object_type=edge.source_object_type,
            source_object_id=edge.source_object_id,
            version=edge.version,
        )
    except KnowledgeGraphError as exc:
        raise BadRequestAppException(str(exc)) from exc


@router.patch(
    "/edges/{edge_id}",
    response_model=GraphEdgeResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_UPDATE))],
)
async def update_graph_edge(
    edge_id: uuid.UUID,
    payload: GraphEdgeUpdateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphEdgeResponse:
    """Update properties of a relationship edge."""
    service = KnowledgeGraphService(db_session)
    try:
        edge = await service.edge_service.get_edge(edge_id, tenant_context.organization_id)
        if payload.status:
            edge = await service.edge_service.repo.update_edge_status(
                edge_id=edge_id,
                organization_id=tenant_context.organization_id,
                status=GraphStatus(payload.status),
            )
        return GraphEdgeResponse(
            id=edge.id,
            organization_id=edge.organization_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            edge_type=edge.edge_type.value,
            weight=edge.weight,
            confidence=edge.confidence,
            is_verified=edge.is_verified,
            status=edge.status.value,
            source_object_type=edge.source_object_type,
            source_object_id=edge.source_object_id,
            version=edge.version,
        )
    except GraphEdgeNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc


@router.post(
    "/edges/{edge_id}/verify",
    response_model=GraphEdgeResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_UPDATE))],
)
async def verify_graph_edge(
    edge_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphEdgeResponse:
    """Certify and verify a relationship edge, boosting confidence to 1.0."""
    service = KnowledgeGraphService(db_session)
    try:
        edge = await service.verify_edge(edge_id, tenant_context.organization_id)
        return GraphEdgeResponse(
            id=edge.id,
            organization_id=edge.organization_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            edge_type=edge.edge_type.value,
            weight=edge.weight,
            confidence=edge.confidence,
            is_verified=edge.is_verified,
            status=edge.status.value,
            source_object_type=edge.source_object_type,
            source_object_id=edge.source_object_id,
            version=edge.version,
        )
    except GraphEdgeNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc


@router.post(
    "/{object_id}/publish",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permission(PERM_GRAPH_PUBLISH))],
)
async def publish_graph_object(
    object_id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """Publish a vertex or edge to production trusted state."""
    service = KnowledgeGraphService(db_session)
    # Check if node first
    node = await service.node_service.repo.get_node(object_id, tenant_context.organization_id)
    if node:
        published_node = await service.publish_node(object_id, tenant_context.organization_id)
        return {"id": str(published_node.id), "type": "node", "status": published_node.status.value}

    # Check edge
    edge = await service.edge_service.repo.get_edge(object_id, tenant_context.organization_id)
    if edge:
        published_edge = await service.publish_edge(object_id, tenant_context.organization_id)
        return {"id": str(published_edge.id), "type": "edge", "status": published_edge.status.value}

    raise NotFoundAppException(f"Graph object '{object_id}' not found.")


@router.post(
    "/sync",
    response_model=GraphSyncResponse,
    dependencies=[Depends(require_permission(PERM_GRAPH_CREATE))],
)
async def sync_knowledge_graph(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GraphSyncResponse:
    """Trigger idempotent synchronization from Semantic Catalog assets."""
    service = KnowledgeGraphService(db_session)
    summary = await service.sync_catalog(tenant_context.organization_id)
    return GraphSyncResponse(
        nodes_created=summary.nodes_created,
        edges_created=summary.edges_created,
        aliases_created=summary.aliases_created,
        skipped=summary.skipped,
    )
