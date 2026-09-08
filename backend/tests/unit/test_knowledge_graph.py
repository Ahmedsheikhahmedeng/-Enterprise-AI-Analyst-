"""Unit tests for Knowledge Graph domain models, algorithms, and services."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.knowledge_graph.application.entity_resolution_service import (
    EntityResolutionService,
)
from app.knowledge_graph.domain.enums import (
    GraphEdgeType,
    GraphNodeType,
    GraphStatus,
    RelationshipConfidenceTier,
    ResolutionStatus,
)
from app.knowledge_graph.domain.models import (
    GraphBudget,
    GraphEdge,
    GraphEntityAlias,
    GraphNode,
)
from app.knowledge_graph.infrastructure.adjacency import AdjacencyEngine
from app.knowledge_graph.infrastructure.cache import KnowledgeGraphCache


def test_graph_node_and_edge_domain_models() -> None:
    """Verify domain representations of graph vertices and directed edges."""
    org_id = uuid.uuid4()
    node_id = uuid.uuid4()

    node = GraphNode(
        id=node_id,
        organization_id=org_id,
        node_type=GraphNodeType.ENTITY,
        name="Customer",
        normalized_name="customer",
        source_object_type="semantic_entity",
        source_object_id=uuid.uuid4(),
        status=GraphStatus.PUBLISHED,
    )
    assert node.name == "Customer"
    assert node.node_type == GraphNodeType.ENTITY
    assert node.status == GraphStatus.PUBLISHED

    tgt_node_id = uuid.uuid4()
    edge = GraphEdge(
        id=uuid.uuid4(),
        organization_id=org_id,
        source_node_id=node_id,
        target_node_id=tgt_node_id,
        edge_type=GraphEdgeType.JOINS_WITH,
        confidence=RelationshipConfidenceTier.EXPLICIT.value,
        is_verified=True,
    )
    assert edge.edge_type == GraphEdgeType.JOINS_WITH
    assert edge.confidence == 0.9
    assert edge.is_verified is True


def test_bounded_path_finding_and_confidence() -> None:
    """Verify BFS path finding and multiplicative confidence calculation."""
    org_id = uuid.uuid4()
    n1 = uuid.uuid4()
    n2 = uuid.uuid4()
    n3 = uuid.uuid4()

    node_map = {
        n1: GraphNode(
            n1, org_id, GraphNodeType.ENTITY, "Customer", "customer", "entity", uuid.uuid4()
        ),
        n2: GraphNode(n2, org_id, GraphNodeType.ENTITY, "Order", "order", "entity", uuid.uuid4()),
        n3: GraphNode(
            n3, org_id, GraphNodeType.METRIC, "Revenue", "revenue", "metric", uuid.uuid4()
        ),
    }

    edges = [
        GraphEdge(
            uuid.uuid4(),
            org_id,
            n1,
            n2,
            GraphEdgeType.JOINS_WITH,
            confidence=1.0,
            is_verified=True,
            status=GraphStatus.PUBLISHED,
        ),
        GraphEdge(
            uuid.uuid4(),
            org_id,
            n2,
            n3,
            GraphEdgeType.MEASURED_BY,
            confidence=0.9,
            is_verified=False,
            status=GraphStatus.PUBLISHED,
        ),
    ]

    engine = AdjacencyEngine(GraphBudget(max_depth=4, max_paths=5))
    paths = engine.find_paths(
        start_node_id=n1,
        target_node_id=n3,
        edges=edges,
        nodes_by_id=node_map,
    )

    assert len(paths) == 1
    p = paths[0]
    assert p.depth == 2
    assert [n.name for n in p.nodes] == ["Customer", "Order", "Revenue"]
    assert p.confidence == 0.9  # 1.0 * 0.9
    assert p.verified_ratio == 0.5  # 1 of 2 is verified


def test_cycle_detection() -> None:
    """Verify cycle detection identifies circular relationships."""
    org_id = uuid.uuid4()
    a = uuid.uuid4()
    b = uuid.uuid4()
    c = uuid.uuid4()

    # Create cycle: A -> B -> C -> A
    edges = [
        GraphEdge(uuid.uuid4(), org_id, a, b, GraphEdgeType.RELATES_TO),
        GraphEdge(uuid.uuid4(), org_id, b, c, GraphEdgeType.RELATES_TO),
        GraphEdge(uuid.uuid4(), org_id, c, a, GraphEdgeType.RELATES_TO),
    ]

    cycles = AdjacencyEngine.detect_cycles(edges)
    assert len(cycles) >= 1
    cycle_nodes = set(cycles[0])
    assert a in cycle_nodes
    assert b in cycle_nodes
    assert c in cycle_nodes


def test_bounded_traversal_depth_limit() -> None:
    """Verify traversal strictly respects max_depth."""
    org_id = uuid.uuid4()
    nodes = [uuid.uuid4() for _ in range(6)]
    node_map = {
        nid: GraphNode(
            nid, org_id, GraphNodeType.ENTITY, f"Node{i}", f"node{i}", "entity", uuid.uuid4()
        )
        for i, nid in enumerate(nodes)
    }

    # Linear chain: 0 -> 1 -> 2 -> 3 -> 4 -> 5
    edges = [
        GraphEdge(uuid.uuid4(), org_id, nodes[i], nodes[i + 1], GraphEdgeType.RELATES_TO)
        for i in range(5)
    ]

    engine = AdjacencyEngine()
    traversal = engine.traverse(
        start_node_id=nodes[0],
        edges=edges,
        nodes_by_id=node_map,
        max_depth=2,  # Should only reach nodes 0, 1, 2
    )

    visited_ids = {n.id for n in traversal.visited_nodes}
    assert nodes[0] in visited_ids
    assert nodes[1] in visited_ids
    assert nodes[2] in visited_ids
    assert nodes[3] not in visited_ids
    assert nodes[4] not in visited_ids


@pytest.mark.asyncio
async def test_multilingual_entity_resolution() -> None:
    """Verify deterministic entity resolution across Arabic, Turkish, and English."""
    mock_session = AsyncMock()
    org_id = uuid.uuid4()
    apple_id = uuid.uuid4()

    apple_node = GraphNode(
        id=apple_id,
        organization_id=org_id,
        node_type=GraphNodeType.ENTITY,
        name="Apple Inc",
        normalized_name="apple inc",
        source_object_type="semantic_entity",
        source_object_id=uuid.uuid4(),
    )

    repo_mock = AsyncMock()
    repo_mock.get_node.return_value = apple_node
    repo_mock.get_node_by_normalized_name.return_value = apple_node

    # Arabic alias
    alias_ar = GraphEntityAlias(
        id=uuid.uuid4(),
        organization_id=org_id,
        entity_node_id=apple_id,
        alias="شركة أبل",
        normalized_alias="شركه ابل",
        language="ar",
        is_verified=True,
    )
    # Turkish alias
    alias_tr = GraphEntityAlias(
        id=uuid.uuid4(),
        organization_id=org_id,
        entity_node_id=apple_id,
        alias="Apple Şirketi",
        normalized_alias="apple şirketi",
        language="tr",
        is_verified=True,
    )

    repo_mock.find_aliases_by_normalized_name.side_effect = lambda org, name: (
        [alias_ar]
        if "ابل" in name
        else ([alias_tr] if "şirket" in name or "sirket" in name else [])
    )

    service = EntityResolutionService(mock_session)
    service.repo = repo_mock

    # 1. English Exact
    res_en = await service.resolve("Apple Inc", org_id)
    assert res_en.status == ResolutionStatus.RESOLVED
    assert res_en.entity_node_id == apple_id
    assert res_en.confidence == 1.0

    # 2. Arabic Alias
    repo_mock.get_node_by_normalized_name.return_value = None
    res_ar = await service.resolve("شركة أبل", org_id)
    assert res_ar.status == ResolutionStatus.RESOLVED
    assert res_ar.entity_node_id == apple_id
    assert res_ar.confidence == 0.95


def test_graph_cache_key_construction() -> None:
    """Verify tenant-isolated cache key generation."""
    org_id = uuid.uuid4()
    key = KnowledgeGraphCache.build_cache_key(org_id, "customer_to_revenue", 3)
    assert f"graph:{org_id}:" in key
    assert ":3" in key
