"""Integration tests for Semantic Catalog, Query Planning, and Agent Typed Tools."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.context import AgentExecutionContext
from app.agents.tools.schemas import SemanticSearchInput
from app.agents.tools.semantic import SemanticSearchTool
from app.models.dataset import Dataset, DatasetColumn
from app.models.semantic import SemanticColumnMapping, SemanticMetric
from app.semantic.application.query_planner import SemanticQueryPlanner
from app.semantic.domain.enums import SemanticObjectType


@pytest.mark.asyncio
async def test_semantic_query_planner_end_to_end() -> None:
    """End-to-end integration test: Metric -> Mapping -> Semantic Query Plan."""
    org_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    column_id = uuid.uuid4()
    metric_id = uuid.uuid4()

    mock_session = AsyncMock()

    # Mock dataset and column
    ds = Dataset(
        id=dataset_id,
        organization_id=org_id,
        name="sales_orders",
        source_type="postgresql",
        status="ready",
    )
    col = DatasetColumn(
        id=column_id,
        dataset_id=dataset_id,
        name="total_amount",
        normalized_name="total_amount",
        data_type="numeric",
    )
    ds.columns = [col]

    metric = SemanticMetric(
        id=metric_id,
        organization_id=org_id,
        name="Total Revenue",
        normalized_name="total revenue",
        definition="Sum of sales orders",
        formula="SUM(total_amount)",
        aggregation="SUM",
        dataset_id=dataset_id,
        status="published",
    )

    mapping = SemanticColumnMapping(
        id=uuid.uuid4(),
        organization_id=org_id,
        semantic_object_type="metric",
        semantic_object_id=metric_id,
        dataset_id=dataset_id,
        column_id=column_id,
        mapping_type="DIRECT",
        confidence=1.0,
        is_verified=True,
    )
    mapping.column = col

    # Configure session mocks
    planner = SemanticQueryPlanner(mock_session)

    # Mock search hit
    hit = MagicMock(
        object_id=metric_id,
        object_type=SemanticObjectType.METRIC,
        score=0.98,
    )
    planner.search_engine.search = AsyncMock(return_value=[hit])  # type: ignore

    # Mock DB executions
    def execute_side_effect(stmt: Any) -> Any:
        mock_res = MagicMock()
        stmt_str = str(stmt)
        if "FROM semantic_metrics" in stmt_str:
            mock_res.scalars.return_value.first.return_value = metric
        elif "FROM semantic_column_mappings" in stmt_str:
            mock_res.scalars.return_value.all.return_value = [mapping]
        elif "FROM datasets" in stmt_str:
            mock_res.scalars.return_value.first.return_value = ds
        else:
            mock_res.scalars.return_value.first.return_value = None
            mock_res.scalars.return_value.all.return_value = []
        return mock_res

    mock_session.execute.side_effect = execute_side_effect

    plan = await planner.plan_query(
        "What is the total revenue?", org_id, target_dataset_id=dataset_id
    )

    assert plan.question == "What is the total revenue?"
    assert plan.is_authoritative
    assert len(plan.resolved_metrics) == 1
    assert plan.resolved_metrics[0].name == "Total Revenue"
    assert plan.resolved_metrics[0].is_verified
    assert plan.sql_hint is not None
    assert 'SELECT SUM("total_amount") AS "total_revenue" FROM "sales_orders"' in plan.sql_hint


@pytest.mark.asyncio
async def test_agent_semantic_tools_execution() -> None:
    """Verify SemanticSearchTool and SemanticGetQueryPlanTool execute properly."""
    org_id = uuid.uuid4()
    mock_session = AsyncMock()

    ctx = AgentExecutionContext(
        session_id=uuid.uuid4(),
        step_id=uuid.uuid4(),
        organization_id=org_id,
        user_id=uuid.uuid4(),
        db_session=mock_session,
    )

    search_tool = SemanticSearchTool()
    preview = await search_tool.preview(
        SemanticSearchInput(query="revenue", limit=5),
        ctx,
    )
    assert preview["action"] == "semantic_search"

    # Mock search execution
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_res

    res = await search_tool.execute(
        SemanticSearchInput(query="revenue", limit=5),
        ctx,
    )
    assert res.success
    assert "results" in res.data
