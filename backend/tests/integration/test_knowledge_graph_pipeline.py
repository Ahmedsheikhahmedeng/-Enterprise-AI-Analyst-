"""Integration tests for Knowledge Graph synchronization, path resolution, and agent tools."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.context import AgentExecutionContext
from app.agents.tools.knowledge_graph import (
    GraphGetNodeTool,
    GraphSearchTool,
)
from app.knowledge_graph.application.graph_service import KnowledgeGraphService
from app.knowledge_graph.domain.enums import (
    GraphEdgeType,
    GraphNodeType,
    GraphStatus,
)
from app.knowledge_graph.domain.models import GraphEdge, GraphNode


@pytest.mark.asyncio
async def test_knowledge_graph_pipeline_sync_and_path_finding() -> None:
    """Test graph pipeline sync, relationship assembly, and path finding end-to-end."""
    org_id = uuid.uuid4()
    mock_session = AsyncMock()

    service = KnowledgeGraphService(mock_session)

    # Mock nodes and edges in repository
    cust_id = uuid.uuid4()
    order_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    rev_id = uuid.uuid4()

    cust_node = GraphNode(
        cust_id,
        org_id,
        GraphNodeType.ENTITY,
        "Customer",
        "customer",
        "entity",
        uuid.uuid4(),
        status=GraphStatus.PUBLISHED,
    )
    order_node = GraphNode(
        order_id,
        org_id,
        GraphNodeType.ENTITY,
        "Order",
        "order",
        "entity",
        uuid.uuid4(),
        status=GraphStatus.PUBLISHED,
    )
    prod_node = GraphNode(
        prod_id,
        org_id,
        GraphNodeType.ENTITY,
        "Product",
        "product",
        "entity",
        uuid.uuid4(),
        status=GraphStatus.PUBLISHED,
    )
    rev_node = GraphNode(
        rev_id,
        org_id,
        GraphNodeType.METRIC,
        "Revenue",
        "revenue",
        "metric",
        uuid.uuid4(),
        status=GraphStatus.PUBLISHED,
    )

    all_nodes = [cust_node, order_node, prod_node, rev_node]
    edges = [
        GraphEdge(
            uuid.uuid4(),
            org_id,
            cust_id,
            order_id,
            GraphEdgeType.JOINS_WITH,
            confidence=1.0,
            is_verified=True,
            status=GraphStatus.PUBLISHED,
        ),
        GraphEdge(
            uuid.uuid4(),
            org_id,
            order_id,
            prod_id,
            GraphEdgeType.JOINS_WITH,
            confidence=1.0,
            is_verified=True,
            status=GraphStatus.PUBLISHED,
        ),
        GraphEdge(
            uuid.uuid4(),
            org_id,
            order_id,
            rev_id,
            GraphEdgeType.MEASURED_BY,
            confidence=0.9,
            is_verified=True,
            status=GraphStatus.PUBLISHED,
        ),
    ]

    service.repo.list_edges = AsyncMock(return_value=edges)  # type: ignore[method-assign]
    service.repo.list_nodes = AsyncMock(return_value=all_nodes)  # type: ignore[method-assign]
    service.repo.get_node = AsyncMock(  # type: ignore[method-assign]
        side_effect=lambda nid, org: next((n for n in all_nodes if n.id == nid), None)
    )

    # Path from Customer to Revenue
    paths = await service.find_paths(
        start_node_id=cust_id,
        target_node_id=rev_id,
        organization_id=org_id,
        max_depth=4,
    )

    assert len(paths) == 1
    p = paths[0]
    assert p.depth == 2
    assert [n.name for n in p.nodes] == ["Customer", "Order", "Revenue"]
    assert p.confidence == 0.9
    assert p.verified_ratio == 1.0


@pytest.mark.asyncio
async def test_agent_graph_tools_execution() -> None:
    """Verify execution of agent graph tools."""
    org_id = uuid.uuid4()
    session_id = uuid.uuid4()
    mock_session = AsyncMock()

    context = AgentExecutionContext(
        session_id=session_id,
        organization_id=org_id,
        db_session=mock_session,
        step_id=uuid.uuid4(),
    )

    node_id = uuid.uuid4()
    test_node = GraphNode(
        id=node_id,
        organization_id=org_id,
        node_type=GraphNodeType.ENTITY,
        name="Orders",
        normalized_name="orders",
        source_object_type="dataset",
        source_object_id=uuid.uuid4(),
        status=GraphStatus.PUBLISHED,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    # 1. Search Tool
    search_tool = GraphSearchTool()
    search_input = await search_tool.validate({"query": "order", "limit": 5})
    # Mock node service listing
    with pytest.MonkeyPatch.context() as mp:
        from app.knowledge_graph.application.node_service import NodeService

        mp.setattr(NodeService, "list_nodes", AsyncMock(return_value=[test_node]))
        output = await search_tool.execute(search_input, context)
        assert output.success is True
        assert output.data["count"] == 1
        assert output.data["nodes"][0]["name"] == "Orders"

    # 2. Get Node Tool
    get_node_tool = GraphGetNodeTool()
    get_node_input = await get_node_tool.validate({"node_id": node_id})
    with pytest.MonkeyPatch.context() as mp:
        from app.knowledge_graph.application.node_service import NodeService

        mp.setattr(NodeService, "get_node", AsyncMock(return_value=test_node))
        output = await get_node_tool.execute(get_node_input, context)
        assert output.success is True
        assert output.data["name"] == "Orders"
        assert output.data["node_type"] == "ENTITY"
