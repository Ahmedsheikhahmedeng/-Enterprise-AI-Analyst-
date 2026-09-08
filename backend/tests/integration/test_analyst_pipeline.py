"""Integration tests for the Unified AI Analyst Orchestrator pipeline.

Tests cross-modal execution across real PostgreSQL test database, RAG document
retrieval, concurrent execution, conflict detection, tenant isolation, and API endpoints.
"""

import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.config import AnalystConfig
from app.analyst.exceptions import AnalystTenantMismatchError
from app.analyst.models import AnalystRouteType
from app.analyst.service import AIAnalystService
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.main import create_app
from app.models.data_source import DataSource
from app.models.organization import Organization
from app.models.user import User
from app.rag.models import Evidence, GroundedAnswer, RAGAnswerResult
from app.rag.service import RAGService
from app.rbac.service import RBACService
from app.sql_agent.providers.deterministic import DeterministicSQLProvider
from app.sql_agent.service import SQLAgentService


@pytest.fixture
async def test_env() -> AsyncGenerator[dict[str, Any], None]:
    """Provide integration environment with real PostgreSQL, initialized tables,
    mock/deterministic RAG service, and AIAnalystService.
    """
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    # 1. Create real test relational tables in PostgreSQL
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS sales ("
                "id SERIAL PRIMARY KEY, "
                "quarter VARCHAR(10) NOT NULL, "
                "year INTEGER NOT NULL, "
                "revenue NUMERIC(15, 2) NOT NULL);"
            )
        )
        await conn.execute(text("TRUNCATE TABLE sales RESTART IDENTITY CASCADE;"))
        await conn.execute(
            text(
                "INSERT INTO sales (quarter, year, revenue) VALUES "
                "('Q1', 2025, 120000000.00), "
                "('Q2', 2025, 135000000.00), "
                "('Q3', 2025, 110000000.00), "
                "('Q4', 2025, 120000000.00);"
            )
        )

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # 2. Configure deterministic SQL Agent
    from app.sql_agent.config import get_sql_agent_config

    sql_cfg = get_sql_agent_config()
    sql_provider = DeterministicSQLProvider()
    sql_service = SQLAgentService(provider=sql_provider, config=sql_cfg)
    app.state.sql_agent_service = sql_service

    # 3. Configure mock/deterministic RAG service
    rag_mock = MagicMock(spec=RAGService)

    async def mock_rag_answer(
        query: str, organization_id: uuid.UUID, **kwargs: Any
    ) -> RAGAnswerResult:
        ev_id = "E1"
        doc_text = (
            "The annual report indicates enterprise demand moderated in Q4, "
            "with reported revenue at 100M."
        )
        return RAGAnswerResult(
            query=query,
            answer=GroundedAnswer(
                answer="Annual report states enterprise demand moderated in Q4 [E1].",
                evidence_ids=[ev_id],
                grounded=True,
                confidence=0.88,
                system_grounding_confidence=0.88,
            ),
            evidence=[
                Evidence(
                    evidence_id=ev_id,
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    organization_id=organization_id,
                    rank=1,
                    rerank_score=0.92,
                    text=doc_text,
                    page_number=15,
                    document_name="Annual_Report_2025.pdf",
                )
            ],
        )

    rag_mock.answer = AsyncMock(side_effect=mock_rag_answer)
    app.state.rag_service = rag_mock

    # 4. Instantiate AIAnalystService
    analyst_cfg = AnalystConfig(
        enabled=True,
        total_timeout_seconds=15.0,
        sql_timeout_seconds=5.0,
        rag_timeout_seconds=5.0,
        max_branches=4,
        max_evidence=15,
    )
    analyst_service = AIAnalystService(
        sql_service=sql_service,
        rag_service=rag_mock,
        config=analyst_cfg,
    )
    app.state.analyst_service = analyst_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
            "sql_service": sql_service,
            "rag_service": rag_mock,
            "analyst_service": analyst_service,
        }

    # Cleanup
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS sales CASCADE;"))
    await engine.dispose()


@pytest.mark.asyncio
class TestAnalystPipelineIntegration:
    """End-to-end integration tests for the AI Analyst orchestrator."""

    async def _setup_org_and_datasource(
        self, session: AsyncSession
    ) -> tuple[Organization, User, DataSource]:
        """Create test organization, user, and registered DataSource with Dataset."""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        ds_id = uuid.uuid4()

        org = Organization(
            id=org_id, name=f"Analyst Org {org_id.hex[:6]}", slug=f"org-{org_id.hex[:6]}"
        )
        user = User(
            id=user_id,
            email=f"analyst-{user_id.hex[:6]}@example.com",
            password_hash="hash",
            first_name="Analyst",
            last_name="User",
            is_active=True,
        )
        ds = DataSource(
            id=ds_id,
            organization_id=org_id,
            created_by=user_id,
            name="Production Sales DB",
            type="postgresql",
            status="active",
            configuration={
                "tables": {
                    "sales": {
                        "description": "Quarterly financial sales data",
                        "row_count": 4,
                        "columns": {
                            "id": {"type": "INTEGER", "is_pk": True},
                            "quarter": {"type": "VARCHAR(10)"},
                            "year": {"type": "INTEGER"},
                            "revenue": {"type": "NUMERIC(15,2)"},
                        },
                    },
                },
            },
        )
        session.add_all([org, user, ds])
        await session.commit()
        return org, user, ds

    async def test_end_to_end_sql_only_analyst(self, test_env: dict[str, Any]) -> None:
        """Verify purely structured question routes to SQL and returns grounded answer."""
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            org, user, ds = await self._setup_org_and_datasource(session)

            res = await analyst_service.ask(
                query="What was total revenue in Q4?",
                organization_id=org.id,
                session=session,
                user_id=user.id,
                datasource_id=ds.id,
            )

            assert res.route == AnalystRouteType.SQL
            assert res.grounded is True
            assert res.is_partial is False
            has_expected_val = (
                "485,000,000.00" in res.answer
                or "total_value" in res.answer
                or "120,000,000.00" in res.answer
            )
            assert has_expected_val
            assert any(c["type"] == "sql" for c in res.citations)

    async def test_end_to_end_rag_only_analyst(self, test_env: dict[str, Any]) -> None:
        """Verify purely document question routes to RAG and returns grounded answer."""
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            org, user, _ = await self._setup_org_and_datasource(session)

            res = await analyst_service.ask(
                query="What does the annual report say about market trends?",
                organization_id=org.id,
                session=session,
                user_id=user.id,
                datasource_id=None,
            )

            assert res.route == AnalystRouteType.RAG
            assert res.grounded is True
            assert any(c["type"] == "document" for c in res.citations)

    async def test_end_to_end_hybrid_analyst_with_conflict_detection(
        self, test_env: dict[str, Any]
    ) -> None:
        """Verify hybrid question executes concurrently and detects conflict."""
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            org, user, ds = await self._setup_org_and_datasource(session)

            query = (
                "Revenue fell in Q4. What was the calculated revenue "
                "and what explanation does the annual report give?"
            )
            res = await analyst_service.ask(
                query=query,
                organization_id=org.id,
                session=session,
                user_id=user.id,
                datasource_id=ds.id,
            )

            assert res.route == AnalystRouteType.HYBRID
            assert res.grounded is True
            assert len(res.evidence) >= 2

            # Check that both SQL and Document citations exist
            citation_types = {c["type"] for c in res.citations}
            assert "sql" in citation_types
            assert "document" in citation_types

            # Check that conflict was detected ($120M SQL vs $100M Document)
            assert len(res.conflicts) >= 1
            assert any("Discrepancy" in c.description for c in res.conflicts)
            assert "Discrepancy" in res.answer or "discrepancy" in res.answer.lower()

    async def test_multi_tenant_isolation_analyst(self, test_env: dict[str, Any]) -> None:
        """Verify Org A cannot query a datasource owned by Org B."""
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            org_a, user_a, _ = await self._setup_org_and_datasource(session)
            org_b, _, ds_b = await self._setup_org_and_datasource(session)

            with pytest.raises(AnalystTenantMismatchError):
                await analyst_service.ask(
                    query="What was total revenue?",
                    organization_id=org_a.id,
                    session=session,
                    user_id=user_a.id,
                    datasource_id=ds_b.id,  # Org B's datasource accessed by Org A
                )

    async def test_partial_failure_handling_sql_error(
        self, test_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that when SQL branch fails, RAG branch result returns degraded."""
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        # Mock SQL service to fail
        err = RuntimeError("SQL execution crashed")
        assert analyst_service.sql_service is not None
        monkeypatch.setattr(
            analyst_service.sql_service, "execute_question", AsyncMock(side_effect=err)
        )

        async with session_factory() as session:
            org, user, ds = await self._setup_org_and_datasource(session)

            query = (
                "Revenue fell in Q4. What was the revenue and what does the annual report explain?"
            )
            res = await analyst_service.ask(
                query=query,
                organization_id=org.id,
                session=session,
                user_id=user.id,
                datasource_id=ds.id,
            )

            assert res.is_partial is True
            assert res.is_degraded is True
            assert res.diagnostics.degraded is True
            assert "partial" in res.answer.lower()


@pytest.mark.asyncio
class TestAnalystAPI:
    """Integration test suite for the REST API endpoint POST /api/v1/analyst/ask."""

    async def test_api_authorized_request(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        org_id = uuid.uuid4()
        user_id = uuid.uuid4()
        ds_id = uuid.uuid4()

        async with session_factory() as session:
            org = Organization(id=org_id, name="API Test Org", slug=f"api-org-{org_id.hex[:6]}")
            user = User(
                id=user_id,
                email=f"api-user-{user_id.hex[:6]}@example.com",
                password_hash="hash",
                first_name="API",
                last_name="User",
                is_active=True,
            )
            ds = DataSource(
                id=ds_id,
                organization_id=org_id,
                created_by=user_id,
                name="Sales DB",
                type="postgresql",
                status="active",
                configuration={
                    "tables": {
                        "sales": {
                            "description": "Sales data",
                            "row_count": 4,
                            "columns": {
                                "id": {"type": "INTEGER", "is_pk": True},
                                "quarter": {"type": "VARCHAR(10)"},
                                "year": {"type": "INTEGER"},
                                "revenue": {"type": "NUMERIC(15,2)"},
                            },
                        },
                    },
                },
            )
            session.add_all([org, user, ds])
            await session.commit()

            from sqlalchemy import select

            from app.models.role import OrganizationMember, Role
            from app.rbac.catalog import ROLE_ANALYST

            role_res = await session.execute(select(Role).where(Role.name == ROLE_ANALYST))
            role = role_res.scalar_one_or_none()
            if not role:
                rbac_svc = RBACService()
                await rbac_svc.seed_system_rbac(session)
                role_res = await session.execute(select(Role).where(Role.name == ROLE_ANALYST))
                role = role_res.scalar_one()

            membership = OrganizationMember(
                organization_id=org_id,
                user_id=user_id,
                role_id=role.id,
            )
            session.add(membership)
            await session.commit()

        token = create_access_token(
            user_id=user_id,
            extra_claims={
                "email": user.email,
                "org_id": str(org_id),
                "role": role.name,
            },
        )

        resp = await client.post(
            "/api/v1/analyst/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "query": "What was total revenue in Q4?",
                "datasource_id": str(ds_id),
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert data["grounded"] is True
        assert len(data["routes"]) >= 1
        assert "diagnostics" in data

    async def test_api_unauthorized_request(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        resp = await client.post(
            "/api/v1/analyst/ask",
            json={"query": "What is the revenue?"},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.asyncio
class TestAnalystPerformanceBenchmark:
    """Latency benchmark for the unified AI analyst orchestration flow."""

    async def test_analyst_latency_benchmark(self, test_env: dict[str, Any]) -> None:
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            org_id = uuid.uuid4()
            user_id = uuid.uuid4()
            ds_id = uuid.uuid4()

            org = Organization(id=org_id, name="Bench Org", slug=f"bench-org-{org_id.hex[:6]}")
            user = User(
                id=user_id,
                email=f"bench-{user_id.hex[:6]}@example.com",
                password_hash="hash",
                first_name="Bench",
                last_name="User",
                is_active=True,
            )
            ds = DataSource(
                id=ds_id,
                organization_id=org_id,
                created_by=user_id,
                name="Bench DB",
                type="postgresql",
                status="active",
                configuration={
                    "tables": {
                        "sales": {
                            "description": "Sales Table",
                            "row_count": 4,
                            "columns": {
                                "id": {"type": "INTEGER", "is_pk": True},
                                "quarter": {"type": "VARCHAR(10)"},
                                "year": {"type": "INTEGER"},
                                "revenue": {"type": "NUMERIC(15,2)"},
                            },
                        },
                    },
                },
            )
            session.add_all([org, user, ds])
            await session.commit()

            t0 = time.perf_counter()
            res = await analyst_service.ask(
                query="Revenue in Q4 and annual report summary?",
                organization_id=org_id,
                session=session,
                user_id=user_id,
                datasource_id=ds_id,
            )
            elapsed = time.perf_counter() - t0

            # Assert execution took less than 1.5 seconds in local test environment
            assert elapsed < 1.5
            assert res.diagnostics.total_ms > 0
            assert res.diagnostics.planning_ms > 0
