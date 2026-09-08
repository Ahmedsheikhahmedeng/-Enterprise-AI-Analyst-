"""Integration tests for canonical Response Orchestration pipeline."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.llm_gateway.application.gateway_service import LLMGatewayService
from app.llm_gateway.infrastructure.providers.deterministic import DeterministicLLMProvider
from app.llm_gateway.infrastructure.registry import ModelRegistry, ProviderRegistry
from app.models.organization import Organization
from app.models.user import User
from app.response_orchestration.application.orchestration_service import (
    ResponseOrchestrationService,
)
from app.response_orchestration.domain.enums import (
    DecisionType,
    OrchestrationMode,
    OrchestrationStatus,
    ResponseStyle,
)
from app.response_orchestration.domain.models import EnterpriseQueryRequest
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


@pytest.fixture
def test_tenant_context() -> TenantContext:
    org_id = uuid.uuid4()
    return TenantContext(
        organization_id=org_id,
        user_id=uuid.uuid4(),
        membership_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        role_name="Admin",
        permissions=frozenset(["orchestration.execute", "orchestration.read"]),
    )


@pytest.fixture
def mock_llm_gateway() -> LLMGatewayService:
    prov_reg = ProviderRegistry()
    model_reg = ModelRegistry()
    det_prov = DeterministicLLMProvider(
        fixed_response="Total revenue for Q3 was $2,000,000 [S1] according to financial statements."
    )
    prov_reg.register("deterministic", lambda: det_prov)
    return LLMGatewayService(provider_registry=prov_reg, model_registry=model_reg)


@pytest.mark.asyncio
async def test_end_to_end_orchestration_flow(
    session: AsyncSession,
    mock_llm_gateway: LLMGatewayService,
) -> None:
    """Verify end-to-end question execution produces structured EnterpriseResponse with provenance."""
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Orch Corp {suffix}", slug=f"orch-{suffix}")
    session.add(org)
    await session.flush()

    user = User(
        email=f"orch_{suffix}@example.com",
        password_hash="argon2_hashed_secret",
        first_name="Orch",
        last_name="User",
    )
    session.add(user)
    await session.flush()

    test_tenant_context = TenantContext(
        organization_id=org.id,
        user_id=user.id,
        membership_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        role_name="Admin",
        permissions=frozenset(["orchestration.execute", "orchestration.read"]),
    )

    class MockSQLAgent:
        async def execute_query(
            self,
            query: str,
            organization_id: uuid.UUID,
            session: AsyncSession,
            datasource_id: uuid.UUID | None = None,
        ) -> Any:
            class Res:
                generated_sql = "SELECT SUM(amount) FROM revenue"
                organization_id = test_tenant_context.organization_id

                class analysis:
                    summary = "Total revenue recorded: $2,000,000."
                    metrics = {"revenue": 2000000.0}

            return Res()

    service = ResponseOrchestrationService(
        sql_service=MockSQLAgent(),  # type: ignore
        rag_service=None,
        llm_gateway=mock_llm_gateway,
    )

    req = EnterpriseQueryRequest(
        question="What was the total revenue in Q3?",
        organization_id=test_tenant_context.organization_id,
        user_id=test_tenant_context.user_id,
        mode=OrchestrationMode.SQL,
        response_style=ResponseStyle.STANDARD,
    )

    res = await service.ask(
        request=req,
        session=session,
        tenant_context=test_tenant_context,
    )

    assert res.execution_id is not None
    assert res.status == OrchestrationStatus.COMPLETED
    assert res.decision == DecisionType.ANSWER
    assert res.confidence_score >= 0.70
    assert len(res.citations) >= 1
    assert res.citations[0].citation_id == "[S1]"
    assert "provenance" in res.__dict__
    assert res.provenance["execution_strategy"] == "SQL_ONLY"


@pytest.mark.asyncio
async def test_preview_query_planning(
    session: AsyncSession,
    test_tenant_context: TenantContext,
) -> None:
    """Verify preview planning returns strategy without executing full synthesis."""
    service = ResponseOrchestrationService()
    plan = await service._plan_reasoning(
        question="Show me revenue by department",
        organization_id=test_tenant_context.organization_id,
        mode=OrchestrationMode.AUTO,
        session=session,
    )
    assert plan.execution_strategy is not None
