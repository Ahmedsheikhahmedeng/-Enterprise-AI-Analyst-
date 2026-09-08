"""Integration tests for Secure SQL Agent & Structured Data Analysis pipeline."""

import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.main import create_app
from app.models.analysis import AnalysisRun, AnalysisStep
from app.models.audit import AuditLog
from app.models.data_source import DataSource
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.usage import LLMRequest, UsageEvent
from app.models.user import User
from app.rbac.catalog import ROLE_ANALYST
from app.rbac.service import RBACService
from app.sql_agent.config import SQLAgentConfig
from app.sql_agent.exceptions import (
    SQLSecurityViolationError,
    SQLTenantMismatchError,
)
from app.sql_agent.providers.deterministic import DeterministicSQLProvider
from app.sql_agent.service import SQLAgentService


@pytest.fixture
async def test_env() -> AsyncGenerator[dict[str, Any], None]:
    """Provide integration environment with real PostgreSQL, initialized tables,
    and SQLAgentService.
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
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS customers ("
                "id SERIAL PRIMARY KEY, "
                "name VARCHAR(255) NOT NULL, "
                "email VARCHAR(255) NOT NULL);"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS orders ("
                "id SERIAL PRIMARY KEY, "
                "customer_id INTEGER NOT NULL, "
                "amount NUMERIC(15, 2) NOT NULL);"
            )
        )
        # Clear previous test data
        await conn.execute(
            text("TRUNCATE TABLE sales, customers, orders RESTART IDENTITY CASCADE;")
        )
        # Seed test records
        await conn.execute(
            text(
                "INSERT INTO sales (quarter, year, revenue) VALUES "
                "('Q1', 2025, 1200000.00), "
                "('Q2', 2025, 1350000.00), "
                "('Q3', 2025, 1100000.00), "
                "('Q4', 2025, 1450000.00);"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO customers (name, email) VALUES "
                "('Acme Corp', 'contact@acme.com'), "
                "('Beta LLC', 'info@beta.com');"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO orders (customer_id, amount) VALUES "
                "(1, 50000.00), "
                "(1, 75000.00), "
                "(2, 120000.00);"
            )
        )

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    cfg = SQLAgentConfig(
        enabled=True,
        provider="deterministic",
        model="deterministic-sql-v1",
        statement_timeout_ms=5000,
        query_timeout_seconds=10.0,
        max_rows=5000,
        max_result_bytes=5_000_000,
        max_joins=5,
        max_ctes=3,
        max_subquery_depth=2,
        schema_cache_ttl_seconds=300,
        prompt_version="sql-v1.0",
        max_llm_cost_per_request=0.10,
    )
    provider = DeterministicSQLProvider()
    sql_service = SQLAgentService(provider=provider, config=cfg)
    app.state.sql_agent_service = sql_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
            "sql_service": sql_service,
        }

    # Clean up test tables
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS sales, customers, orders CASCADE;"))
    await dispose_database_engine(engine)


async def _seed_user_and_org(
    session: AsyncSession,
    org_name: str = "Test SQL Org",
    role_name: str = ROLE_ANALYST,
) -> tuple[User, Organization, str]:
    """Helper to create tenant organization, analyst user, and JWT auth token."""
    org_uid = uuid.uuid4().hex[:8]
    org = Organization(name=org_name, slug=f"org-{org_uid}")
    session.add(org)
    await session.commit()
    await session.refresh(org)

    uid = uuid.uuid4().hex[:8]
    user = User(
        email=f"analyst_{uid}@example.com",
        password_hash=hash_password("StrongP@ssw0rd123!"),
        first_name="SQL",
        last_name=f"Analyst {uid}",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    role_res = await session.execute(select(Role).where(Role.name == role_name))
    role = role_res.scalar_one_or_none()
    if not role:
        rbac_svc = RBACService()
        await rbac_svc.seed_system_rbac(session)
        role_res = await session.execute(select(Role).where(Role.name == role_name))
        role = role_res.scalar_one()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role_id=role.id,
    )
    session.add(membership)
    await session.commit()

    token = create_access_token(
        user_id=user.id,
        extra_claims={
            "email": user.email,
            "org_id": str(org.id),
            "role": role.name,
        },
    )
    return user, org, token


async def _create_test_datasource(
    session: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str = "Corporate ERP Database",
) -> DataSource:
    """Helper to create verified DataSource with tables in PostgreSQL."""
    ds = DataSource(
        name=name,
        type="postgresql",
        status="active",
        organization_id=org_id,
        created_by=user_id,
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
                "customers": {
                    "description": "Enterprise customer accounts",
                    "row_count": 2,
                    "columns": {
                        "id": {"type": "INTEGER", "is_pk": True},
                        "name": {"type": "VARCHAR(255)"},
                        "email": {"type": "VARCHAR(255)"},
                    },
                },
                "orders": {
                    "description": "Customer purchase orders",
                    "row_count": 3,
                    "columns": {
                        "id": {"type": "INTEGER", "is_pk": True},
                        "customer_id": {"type": "INTEGER"},
                        "amount": {"type": "NUMERIC(15,2)"},
                    },
                },
            },
            "relationships": [
                {
                    "from_table": "orders",
                    "from_column": "customer_id",
                    "to_table": "customers",
                    "to_column": "id",
                }
            ],
        },
    )
    session.add(ds)
    await session.commit()
    await session.refresh(ds)
    return ds


class TestSQLAgentPipelineIntegration:
    """End-to-end integration tests for Secure SQL Agent workflow."""

    @pytest.mark.asyncio
    async def test_end_to_end_sql_agent_execution(self, test_env: dict[str, Any]) -> None:
        """Verify full query pipeline:
        question -> plan -> generate -> validate -> execute -> analyze.
        """
        async with test_env["session_factory"]() as session:
            user, org, _ = await _seed_user_and_org(session)
            ds = await _create_test_datasource(session, org.id, user.id)

            sql_service: SQLAgentService = test_env["sql_service"]
            result = await sql_service.execute_question(
                question="What was total revenue by quarter in 2025?",
                datasource_id=ds.id,
                organization_id=org.id,
                session=session,
                user_id=user.id,
            )

            assert result.query_result.row_count == 4
            assert "quarter" in result.query_result.columns
            assert "total_revenue" in result.query_result.columns

            # Verify analytical computation
            assert result.analysis is not None
            assert result.analysis.metrics["total_revenue_sum"] == 5100000.0
            assert result.analysis.metrics["total_revenue_avg"] == 1275000.0

            # Verify provenance
            assert len(result.provenance.sql_hash) == 64
            assert "sales" in result.provenance.tables_used

    @pytest.mark.asyncio
    async def test_multi_tenant_isolation_datasource(self, test_env: dict[str, Any]) -> None:
        """Verify Org A cannot query DataSource belonging to Org B."""
        async with test_env["session_factory"]() as session:
            user_a, org_a, _ = await _seed_user_and_org(session, "Org A")
            user_b, org_b, _ = await _seed_user_and_org(session, "Org B")

            ds_b = await _create_test_datasource(session, org_b.id, user_b.id, "Org B Database")

            sql_service: SQLAgentService = test_env["sql_service"]

            # Org A tries to query Org B's datasource
            with pytest.raises(SQLTenantMismatchError):
                await sql_service.execute_question(
                    question="What was total revenue by quarter in 2025?",
                    datasource_id=ds_b.id,
                    organization_id=org_a.id,
                    session=session,
                    user_id=user_a.id,
                )

    @pytest.mark.asyncio
    async def test_read_only_security_blocks_malicious_write(
        self, test_env: dict[str, Any]
    ) -> None:
        """Verify write operations (DELETE FROM sales) are blocked by AST validator."""
        async with test_env["session_factory"]() as session:
            user, org, _ = await _seed_user_and_org(session)
            ds = await _create_test_datasource(session, org.id, user.id)

            sql_service: SQLAgentService = test_env["sql_service"]

            # Deterministic provider will generate 'DELETE FROM sales;'
            with pytest.raises(SQLSecurityViolationError):
                await sql_service.execute_question(
                    question="delete from sales",
                    datasource_id=ds.id,
                    organization_id=org.id,
                    session=session,
                    user_id=user.id,
                )

            # Verify sales records were not deleted
            check = await session.execute(text("SELECT COUNT(*) FROM sales;"))
            assert check.scalar() == 4

    @pytest.mark.asyncio
    async def test_row_limit_enforcement(self, test_env: dict[str, Any]) -> None:
        """Verify limit parameter bounds returned rows and sets truncated flag."""
        async with test_env["session_factory"]() as session:
            user, org, _ = await _seed_user_and_org(session)
            ds = await _create_test_datasource(session, org.id, user.id)

            sql_service: SQLAgentService = test_env["sql_service"]
            result = await sql_service.execute_question(
                question="What was total revenue by quarter in 2025?",
                datasource_id=ds.id,
                organization_id=org.id,
                session=session,
                user_id=user.id,
                limit=2,
            )

            assert result.query_result.row_count == 2
            assert result.query_result.truncated is True

    @pytest.mark.asyncio
    async def test_provenance_and_audit_persistence(self, test_env: dict[str, Any]) -> None:
        """Verify AuditLog, LLMRequest, UsageEvent, and AnalysisSteps are recorded."""
        async with test_env["session_factory"]() as session:
            user, org, _ = await _seed_user_and_org(session)
            ds = await _create_test_datasource(session, org.id, user.id)

            run = AnalysisRun(
                organization_id=org.id,
                user_id=user.id,
                query="What was total revenue by quarter in 2025?",
                status="running",
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)

            sql_service: SQLAgentService = test_env["sql_service"]
            result = await sql_service.execute_question(
                question="What was total revenue by quarter in 2025?",
                datasource_id=ds.id,
                organization_id=org.id,
                session=session,
                user_id=user.id,
                analysis_run_id=run.id,
            )

            # Verify AuditLog
            audit_stmt = select(AuditLog).where(
                AuditLog.organization_id == org.id,
                AuditLog.action == "sql_agent.query_execute",
            )
            audit_res = await session.execute(audit_stmt)
            audit_entry = audit_res.scalar_one_or_none()
            assert audit_entry is not None
            assert audit_entry.resource_id == str(ds.id)
            assert audit_entry.metadata_["sql_hash"] == result.provenance.sql_hash

            # Verify LLMRequest
            llm_stmt = select(LLMRequest).where(LLMRequest.organization_id == org.id)
            llm_res = await session.execute(llm_stmt)
            llm_entry = llm_res.scalar_one_or_none()
            assert llm_entry is not None
            assert llm_entry.model == "deterministic-sql-v1"

            # Verify UsageEvent
            usage_stmt = select(UsageEvent).where(
                UsageEvent.organization_id == org.id,
                UsageEvent.event_type == "sql_agent_query",
            )
            usage_res = await session.execute(usage_stmt)
            usage_entry = usage_res.scalar_one_or_none()
            assert usage_entry is not None

            # Verify AnalysisSteps
            step_stmt = select(AnalysisStep).where(AnalysisStep.analysis_run_id == run.id)
            step_res = await session.execute(step_stmt)
            steps = step_res.scalars().all()
            assert len(steps) == 2
            assert {s.step_type for s in steps} == {"sql_planning", "sql_execution"}


class TestSQLAgentAPI:
    """REST API endpoint tests for POST /api/v1/sql/query."""

    @pytest.mark.asyncio
    async def test_api_answer_endpoint_success(self, test_env: dict[str, Any]) -> None:
        """Verify successful authenticated request to POST /api/v1/sql/query."""
        async with test_env["session_factory"]() as session:
            user, org, token = await _seed_user_and_org(session)
            ds = await _create_test_datasource(session, org.id, user.id)

        client: AsyncClient = test_env["client"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-Id": str(org.id),
        }
        payload = {
            "query": "What was total revenue by quarter in 2025?",
            "datasource_id": str(ds.id),
            "limit": 100,
            "analyze": True,
        }

        resp = await client.post("/api/v1/sql/query", headers=headers, json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert "SELECT" in data["sql"]
        assert data["query_result"]["row_count"] == 4
        assert data["analysis"] is not None
        assert "provenance" in data
        assert len(data["provenance"]["sql_hash"]) == 64

    @pytest.mark.asyncio
    async def test_api_unauthorized_request(self, test_env: dict[str, Any]) -> None:
        """Verify request without Authorization header returns 401."""
        client: AsyncClient = test_env["client"]
        payload = {
            "query": "What was total revenue by quarter in 2025?",
            "datasource_id": str(uuid.uuid4()),
        }
        resp = await client.post("/api/v1/sql/query", json=payload)
        assert resp.status_code in (401, 403)


class TestSQLPerformanceBenchmark:
    """Performance benchmarks measuring sub-millisecond component latencies."""

    @pytest.mark.asyncio
    async def test_sql_agent_latency_benchmark(self, test_env: dict[str, Any]) -> None:
        """Measure individual stages and total pipeline latency."""
        async with test_env["session_factory"]() as session:
            user, org, _ = await _seed_user_and_org(session)
            ds = await _create_test_datasource(session, org.id, user.id)

            sql_service: SQLAgentService = test_env["sql_service"]

            t0 = time.perf_counter()
            result = await sql_service.execute_question(
                question="What was total revenue by quarter in 2025?",
                datasource_id=ds.id,
                organization_id=org.id,
                session=session,
                user_id=user.id,
            )
            total_elapsed_ms = (time.perf_counter() - t0) * 1000

            diag = result.diagnostics
            print("\n--- SQL Agent Performance Benchmark ---")
            print(f"Schema Discovery: {diag.get('schema_discovery_ms', 0):.2f} ms")
            print(f"Planning:         {diag.get('planning_ms', 0):.2f} ms")
            print(f"Generation:       {diag.get('generation_ms', 0):.2f} ms")
            print(f"AST Validation:   {diag.get('validation_ms', 0):.2f} ms")
            print(f"DB Execution:     {diag.get('execution_ms', 0):.2f} ms")
            print(f"Pandas Analysis:  {diag.get('analysis_ms', 0):.2f} ms")
            print(f"Total Pipeline:   {total_elapsed_ms:.2f} ms")

            assert total_elapsed_ms < 500.0
