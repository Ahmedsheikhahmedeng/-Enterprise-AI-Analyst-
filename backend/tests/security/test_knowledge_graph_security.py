"""Security and tenant isolation tests for Knowledge Graph and Relationship Reasoning."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.knowledge_graph.application.edge_service import EdgeService
from app.knowledge_graph.domain.enums import GraphEdgeType, GraphNodeType, GraphStatus
from app.knowledge_graph.domain.errors import (
    CrossTenantGraphViolationError,
)
from app.knowledge_graph.domain.models import GraphBudget, GraphEdge, GraphNode
from app.knowledge_graph.infrastructure.adjacency import AdjacencyEngine
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository


@pytest.mark.asyncio
async def test_cross_tenant_edge_creation_prevention() -> None:
    """Verify an attacker cannot connect an Org A node to an Org B node."""
    org_a = uuid.uuid4()
    node_a_id = uuid.uuid4()
    foreign_node_b_id = uuid.uuid4()

    mock_session = AsyncMock()
    repo = KnowledgeGraphRepository(mock_session)

    node_a = GraphNode(
        id=node_a_id,
        organization_id=org_a,
        node_type=GraphNodeType.ENTITY,
        name="OrgA_Customer",
        normalized_name="orga_customer",
        source_object_type="semantic_entity",
        source_object_id=uuid.uuid4(),
    )

    # Mock get_node: returns node_a for Org A, but returns None when looking up foreign_node_b for Org A
    async def mock_get_node(node_id: uuid.UUID, organization_id: uuid.UUID) -> GraphNode | None:
        if node_id == node_a_id and organization_id == org_a:
            return node_a
        return None

    repo.get_node = mock_get_node  # type: ignore[method-assign]

    edge_service = EdgeService(mock_session)

    edge_service.repo = repo

    with pytest.raises(
        CrossTenantGraphViolationError, match="Target node .* does not belong to organization"
    ):
        await edge_service.create_edge(
            organization_id=org_a,
            source_node_id=node_a_id,
            target_node_id=foreign_node_b_id,
            edge_type=GraphEdgeType.JOINS_WITH,
        )


@pytest.mark.asyncio
async def test_cross_tenant_node_lookup_returns_none() -> None:
    """Verify tenant cannot retrieve another tenant's vertex."""
    org_a = uuid.uuid4()
    target_node_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    # Query scoped to org_a returns None
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    repo = KnowledgeGraphRepository(mock_session)
    node = await repo.get_node(target_node_id, organization_id=org_a)
    assert node is None


def test_traversal_budget_bounds_enforced() -> None:
    """Verify that graph traversal engine enforces hard caps on depth and visited nodes."""
    org_id = uuid.uuid4()
    nodes = [uuid.uuid4() for _ in range(100)]
    node_map = {
        nid: GraphNode(
            nid, org_id, GraphNodeType.ENTITY, f"Node{i}", f"node{i}", "entity", uuid.uuid4()
        )
        for i, nid in enumerate(nodes)
    }

    # High-branching fanout tree
    edges = [
        GraphEdge(uuid.uuid4(), org_id, nodes[0], nodes[i], GraphEdgeType.RELATES_TO)
        for i in range(1, 100)
    ]

    budget = GraphBudget(max_depth=1, max_nodes=10)
    engine = AdjacencyEngine(budget)
    traversal = engine.traverse(
        start_node_id=nodes[0],
        edges=edges,
        nodes_by_id=node_map,
        max_depth=1,
        max_nodes=10,
    )

    # Visited nodes should not exceed budget limit
    assert len(traversal.visited_nodes) <= 10


def test_unverified_relationships_filtered_in_trusted_mode() -> None:
    """Verify that trusted reasoning mode excludes unverified edges."""
    org_id = uuid.uuid4()
    n1 = uuid.uuid4()
    n2 = uuid.uuid4()

    node_map = {
        n1: GraphNode(
            n1, org_id, GraphNodeType.ENTITY, "Customer", "customer", "entity", uuid.uuid4()
        ),
        n2: GraphNode(
            n2, org_id, GraphNodeType.METRIC, "Revenue", "revenue", "metric", uuid.uuid4()
        ),
    }

    # Only unverified edge exists
    edges = [
        GraphEdge(
            uuid.uuid4(),
            org_id,
            n1,
            n2,
            GraphEdgeType.MEASURED_BY,
            confidence=0.6,
            is_verified=False,
            status=GraphStatus.DRAFT,
        )
    ]

    engine = AdjacencyEngine()
    # In only_verified=True mode, no path should be returned
    paths = engine.find_paths(
        start_node_id=n1,
        target_node_id=n2,
        edges=edges,
        nodes_by_id=node_map,
        only_verified=True,
    )
    assert len(paths) == 0
