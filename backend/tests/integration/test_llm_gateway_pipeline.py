"""Integration tests verifying RAG, SQL Agent, Evaluation Judge, and Agent Planner integration with LLM Gateway."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.providers.base import OptionalLLMAgentPlanner
from app.agents.schemas import AgentType
from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.evaluation.scorers.llm_judge import GatewayJudgeProvider
from app.llm_gateway.application.gateway_service import LLMGatewayService
from app.llm_gateway.domain.enums import LLMTaskType, MessageRole
from app.llm_gateway.domain.models import LLMMessage, LLMRequestPayload
from app.models.organization import Organization
from app.models.usage import LLMRequest
from app.rag.providers.gateway import GatewayRAGProvider
from app.sql_agent.models import ColumnSchema, SchemaContext, TableSchema
from app.sql_agent.planner import SQLPlan
from app.sql_agent.providers.gateway import GatewaySQLProvider
from app.tenancy.context import TenantContext


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide isolated async database session with automatic transaction rollback."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as s:
        try:
            yield s
        finally:
            await s.rollback()
            await s.close()
    await dispose_database_engine(engine)


@pytest.mark.asyncio
async def test_rag_gateway_integration() -> None:
    """Verify RAG provider invokes LLM Gateway and returns structured RAGProviderResponse."""
    gateway = LLMGatewayService()
    rag_provider = GatewayRAGProvider(gateway_service=gateway, model_name="mock-model")

    resp = await rag_provider.generate(
        system_prompt="Answer based on evidence.",
        user_prompt="What is quarterly revenue?",
        max_tokens=256,
    )

    assert resp.answer is not None
    assert len(resp.answer) > 0
    assert resp.model == "mock-model"
    assert resp.latency_ms >= 0


@pytest.mark.asyncio
async def test_sql_agent_gateway_integration() -> None:
    """Verify SQL Agent provider invokes LLM Gateway with structured schema output."""
    gateway = LLMGatewayService()
    sql_provider = GatewaySQLProvider(gateway_service=gateway, model_name="mock-model")

    schema_ctx = SchemaContext(
        datasource_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        dialect="postgresql",
        tables={
            "customers": TableSchema(
                name="customers",
                columns=[
                    ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
                    ColumnSchema(name="name", data_type="VARCHAR"),
                ],
            )
        },
    )
    plan = SQLPlan(
        question="List all customers",
        target_tables=["customers"],
        suggested_aggregations=[],
        filter_hints=[],
        max_limit=50,
    )

    resp = await sql_provider.generate_sql(plan=plan, schema_context=schema_ctx)
    assert resp.generated_sql is not None
    assert "SELECT" in resp.generated_sql.sql.upper()
    assert resp.generated_sql.confidence > 0.0


@pytest.mark.asyncio
async def test_evaluation_judge_gateway_integration() -> None:
    """Verify Evaluation Judge qualitative evaluation routed through LLM Gateway."""
    gateway = LLMGatewayService()
    judge = GatewayJudgeProvider(
        gateway_service=gateway, model_name="mock-model", prompt_version="v2"
    )

    result = await judge.evaluate(
        query="What were the Q3 profits?",
        answer="Q3 profits grew by 15% according to financial disclosures.",
        evidence_texts=["Financial disclosure confirms 15% profit growth in Q3."],
    )

    assert result.score > 0.0
    assert result.label in ("excellent", "good", "marginal", "poor")
    assert result.metadata.get("judge_prompt_version") == "v2"


@pytest.mark.asyncio
async def test_agent_planner_gateway_integration() -> None:
    """Verify Agent Planner creates valid step sequence through LLM Gateway."""
    planner = OptionalLLMAgentPlanner()
    steps = await planner.generate_plan(
        goal="Analyze customer churn",
        agent_type=AgentType.ANALYST_AGENT,
        max_steps=5,
    )
    assert len(steps) >= 1
    assert steps[0].sequence == 1
    assert steps[0].tool_name is not None


@pytest.mark.asyncio
async def test_gateway_usage_persistence(session: AsyncSession) -> None:
    """Verify Gateway execution creates an audit record in the llm_requests table."""
    from app.models.user import User

    org = Organization(
        id=uuid.uuid4(),
        name="Gateway Test Tenant",
        slug=f"tenant-gw-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    session.add(org)

    user = User(
        id=uuid.uuid4(),
        email=f"gw-user-{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashed_pw",
        first_name="Gateway",
        last_name="Tester",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    tenant_ctx = TenantContext(
        organization_id=org.id,
        user_id=user.id,
        membership_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        role_name="Admin",
        permissions=frozenset(["llm.read"]),
    )

    gateway = LLMGatewayService()
    payload = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Hello enterprise model")],
        task_type=LLMTaskType.RAG_ANSWER,
        pinned_model="mock-model",
    )

    response = await gateway.generate(
        payload=payload,
        tenant_context=tenant_ctx,
        session=session,
    )
    assert response.content is not None

    # Query LLMRequest table to verify persistence
    stmt = select(LLMRequest).where(LLMRequest.organization_id == org.id)
    res = await session.execute(stmt)
    entry = res.scalar_one_or_none()

    assert entry is not None
    assert entry.provider == "deterministic"
    assert entry.model == "mock-model"
    assert entry.task_type == "rag_answer"
    assert entry.status == "success"
