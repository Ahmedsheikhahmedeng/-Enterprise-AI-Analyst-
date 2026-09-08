"""Integration tests for Enterprise AI Evaluation & Quality Framework.

Validates end-to-end evaluation lifecycle:
- Dataset creation and versioning
- Ground-truth evaluation cases across SQL, RAG, and Hybrid modalities
- Benchmark execution against the unified analyst pipeline
- Fine-grained case results and Scorecard generation
- Comparative regression detection against baselines
- Strict multi-tenant isolation and RBAC role restrictions (Admin vs Viewer)
- Complete audit logging verification
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.config import get_analyst_config
from app.analyst.service import AIAnalystService
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.evaluation.service import EvaluationService
from app.main import create_app
from app.models.audit import AuditLog
from app.models.data_source import DataSource
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rag.models import Evidence, GroundedAnswer, RAGAnswerResult
from app.rag.service import RAGService
from app.rbac.catalog import ROLE_ADMIN, ROLE_VIEWER
from app.rbac.service import RBACService
from app.sql_agent.config import get_sql_agent_config
from app.sql_agent.providers.deterministic import DeterministicSQLProvider
from app.sql_agent.service import SQLAgentService


@pytest.fixture
async def test_env() -> AsyncGenerator[dict[str, Any], None]:
    """Set up real database engine, tables, analyst services, evaluation engine, and test client."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    # Seed sales table for deterministic SQL queries
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

    # 1. Deterministic SQL Service
    sql_cfg = get_sql_agent_config()
    sql_provider = DeterministicSQLProvider()
    sql_service = SQLAgentService(provider=sql_provider, config=sql_cfg)
    app.state.sql_agent_service = sql_service

    # 2. Mock RAG Service with deterministic evidence
    rag_mock = MagicMock(spec=RAGService)

    async def mock_rag_answer(
        query: str, organization_id: uuid.UUID, **kwargs: Any
    ) -> RAGAnswerResult:
        ev_id = "R1"
        doc_text = (
            "Annual report states enterprise revenue declined by 12% in Q4 "
            "due to supply constraints [R1]."
        )
        return RAGAnswerResult(
            query=query,
            answer=GroundedAnswer(
                answer=doc_text,
                evidence_ids=[ev_id],
                grounded=True,
                confidence=0.95,
                system_grounding_confidence=0.95,
            ),
            evidence=[
                Evidence(
                    evidence_id=ev_id,
                    chunk_id=uuid.uuid4(),
                    document_id=uuid.uuid4(),
                    organization_id=organization_id,
                    rank=1,
                    rerank_score=0.95,
                    text=doc_text,
                    page_number=4,
                    document_name="annual_report_2025.pdf",
                )
            ],
        )

    rag_mock.answer.side_effect = mock_rag_answer
    app.state.rag_service = rag_mock

    # 3. AI Analyst Orchestrator
    analyst_service = AIAnalystService(
        sql_service=sql_service,
        rag_service=rag_mock,
        config=get_analyst_config(),
    )
    app.state.analyst_service = analyst_service

    # 4. Evaluation Service
    evaluation_service = EvaluationService()
    app.state.evaluation_service = evaluation_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
            "analyst_service": analyst_service,
            "evaluation_service": evaluation_service,
        }

    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS sales CASCADE;"))
    await engine.dispose()


class TestEvaluationIntegrationPipeline:
    """End-to-end integration tests for the Enterprise Evaluation & Quality Framework."""

    async def _setup_org_and_user(
        self, session: AsyncSession, role_name: str = ROLE_ADMIN
    ) -> tuple[Organization, User, str]:
        """Create tenant organization, user with role, and signed JWT token."""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()

        org = Organization(
            id=org_id,
            name=f"Eval Org {org_id.hex[:6]}",
            slug=f"eval-org-{org_id.hex[:6]}",
        )
        session.add(org)

        user = User(
            id=user_id,
            email=f"eval_{user_id.hex[:8]}@example.com",
            first_name="Eval",
            last_name="Tester",
            password_hash="test_hash",
            is_active=True,
        )
        session.add(user)
        await session.flush()

        rbac_svc = RBACService()
        await rbac_svc.seed_system_rbac(session)
        role_res = await session.execute(select(Role).where(Role.name == role_name))
        role = role_res.scalar_one()

        membership = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role_id=role.id,
        )
        session.add(membership)
        await session.commit()

        token = create_access_token(
            user_id=user.id,
            extra_claims={"org_id": str(org_id), "role": role_name, "email": user.email},
        )
        return org, user, token

    async def _setup_datasource(
        self, session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID
    ) -> DataSource:
        """Register PostgreSQL datasource for testing."""
        ds = DataSource(
            organization_id=org_id,
            name="Test Sales DB",
            type="postgresql",
            status="active",
            configuration={"database": "testdb"},
            created_by=user_id,
        )
        session.add(ds)
        await session.commit()
        await session.refresh(ds)
        return ds

    @pytest.mark.asyncio
    async def test_dataset_and_case_lifecycle(self, test_env: dict[str, Any]) -> None:
        """Test creating datasets, adding versioned test cases, and listing."""
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            org, user, token = await self._setup_org_and_user(session, ROLE_ADMIN)
            ds = await self._setup_datasource(session, org.id, user.id)

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create dataset
        ds_resp = await client.post(
            "/api/v1/evaluation/datasets",
            json={
                "name": "Enterprise Benchmark Suite",
                "description": "Benchmark cases covering SQL, RAG, and Hybrid questions",
                "language": "en",
            },
            headers=headers,
        )
        assert ds_resp.status_code == 201
        dataset_data = ds_resp.json()
        dataset_id = dataset_data["id"]
        assert dataset_data["name"] == "Enterprise Benchmark Suite"
        assert dataset_data["version"] == 1

        # 2. Add SQL Case
        sql_case_resp = await client.post(
            f"/api/v1/evaluation/datasets/{dataset_id}/cases",
            json={
                "query": "What was total revenue in Q4?",
                "route_expected": "sql",
                "datasource_id": str(ds.id),
                "expected_answer": "Total revenue in Q4 was $120,000,000.",
                "expected_metrics": {"revenue": 120000000},
                "tags": ["financial", "revenue"],
                "difficulty": "easy",
            },
            headers=headers,
        )
        assert sql_case_resp.status_code == 201
        assert sql_case_resp.json()["route_expected"] == "sql"

        # 3. Add RAG Case
        rag_case_resp = await client.post(
            f"/api/v1/evaluation/datasets/{dataset_id}/cases",
            json={
                "query": "What explains the decline in Q4 revenue?",
                "route_expected": "rag",
                "expected_documents": ["annual_report_2025.pdf"],
                "expected_citations": ["R1"],
                "expected_answer": "Revenue declined due to supply constraints.",
                "tags": ["qualitative", "annual_report"],
                "difficulty": "medium",
            },
            headers=headers,
        )
        assert rag_case_resp.status_code == 201
        assert rag_case_resp.json()["route_expected"] == "rag"

        # 4. Add Hybrid Case
        hybrid_case_resp = await client.post(
            f"/api/v1/evaluation/datasets/{dataset_id}/cases",
            json={
                "query": "Compare Q4 revenue with annual report findings",
                "route_expected": "hybrid",
                "datasource_id": str(ds.id),
                "expected_documents": ["annual_report_2025.pdf"],
                "expected_metrics": {"revenue": 120000000},
                "tags": ["hybrid", "cross_source"],
                "difficulty": "hard",
            },
            headers=headers,
        )
        assert hybrid_case_resp.status_code == 201

        # 5. List Cases
        list_cases_resp = await client.get(
            f"/api/v1/evaluation/datasets/{dataset_id}/cases",
            headers=headers,
        )
        assert list_cases_resp.status_code == 200
        cases_list = list_cases_resp.json()
        assert cases_list["total"] == 3
        assert len(cases_list["items"]) == 3

    @pytest.mark.asyncio
    async def test_benchmark_execution_scorecard_and_regression(
        self, test_env: dict[str, Any]
    ) -> None:
        """Run benchmark suite against AIAnalystService, verify scorecard and regression comparison."""
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            org, user, token = await self._setup_org_and_user(session, ROLE_ADMIN)
            ds = await self._setup_datasource(session, org.id, user.id)

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create dataset and seed deterministic cases
        ds_resp = await client.post(
            "/api/v1/evaluation/datasets",
            json={"name": "End-to-End Suite", "language": "en"},
            headers=headers,
        )
        dataset_id = ds_resp.json()["id"]

        # Case 1: SQL Case
        await client.post(
            f"/api/v1/evaluation/datasets/{dataset_id}/cases",
            json={
                "query": "What was total revenue in Q4?",
                "route_expected": "sql",
                "datasource_id": str(ds.id),
                "expected_metrics": {"revenue": 120000000},
            },
            headers=headers,
        )

        # Case 2: RAG Case
        await client.post(
            f"/api/v1/evaluation/datasets/{dataset_id}/cases",
            json={
                "query": "What explains the decline in Q4 revenue?",
                "route_expected": "rag",
                "expected_citations": ["R1"],
                "expected_documents": ["annual_report_2025.pdf"],
            },
            headers=headers,
        )

        # 2. Run Benchmark (Baseline Run)
        run_resp = await client.post(
            "/api/v1/evaluation/runs",
            json={"dataset_id": dataset_id},
            headers=headers,
        )
        assert run_resp.status_code == 201
        run_data = run_resp.json()
        baseline_run_id = run_data["id"]
        assert run_data["status"] == "completed"
        assert run_data["total_cases"] == 2
        assert run_data["git_commit"] != ""

        # 3. Retrieve Case Results
        results_resp = await client.get(
            f"/api/v1/evaluation/runs/{baseline_run_id}/results",
            headers=headers,
        )
        assert results_resp.status_code == 200
        results = results_resp.json()
        assert len(results) == 2
        assert any(r["expected_route"] == "sql" for r in results)
        assert any(r["expected_route"] == "rag" for r in results)

        # 4. Generate Scorecard
        scorecard_resp = await client.get(
            f"/api/v1/evaluation/runs/{baseline_run_id}/scorecard",
            headers=headers,
        )
        assert scorecard_resp.status_code == 200
        scorecard = scorecard_resp.json()
        assert scorecard["total_cases"] == 2
        assert scorecard["pass_rate"] >= 0.5
        assert "quality_score" in scorecard["segmented_scores"]
        assert "performance_score" in scorecard["segmented_scores"]
        assert "p95_ms" in scorecard["latency"]

        # 5. Run Candidate Benchmark
        cand_resp = await client.post(
            "/api/v1/evaluation/runs",
            json={"dataset_id": dataset_id},
            headers=headers,
        )
        assert cand_resp.status_code == 201
        candidate_run_id = cand_resp.json()["id"]

        # 6. Compare Candidate vs Baseline (Regression Detection)
        compare_resp = await client.post(
            f"/api/v1/evaluation/runs/{candidate_run_id}/compare",
            json={"baseline_run_id": baseline_run_id},
            headers=headers,
        )
        assert compare_resp.status_code == 200
        comparison = compare_resp.json()
        assert comparison["status"] in ("PASS", "WARNING", "FAIL")
        assert "quality_delta" in comparison["deltas"]
        assert comparison["new_failures_count"] == 0

    @pytest.mark.asyncio
    async def test_tenant_isolation_and_rbac(self, test_env: dict[str, Any]) -> None:
        """Verify cross-tenant boundary isolation and RBAC viewer restrictions."""
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        # Set up Org A (Admin), Org B (Admin), and Org A (Viewer)
        async with session_factory() as session:
            org_a, _, token_a_admin = await self._setup_org_and_user(session, ROLE_ADMIN)
            org_b, _, token_b_admin = await self._setup_org_and_user(session, ROLE_ADMIN)

            # Add a Viewer to Org A
            viewer_user = User(
                id=uuid.uuid4(),
                email=f"viewer_{uuid.uuid4().hex[:8]}@example.com",
                first_name="Viewer",
                last_name="User",
                password_hash="test_hash",
                is_active=True,
            )
            session.add(viewer_user)
            await session.flush()

            role_res = await session.execute(select(Role).where(Role.name == ROLE_VIEWER))
            viewer_role = role_res.scalar_one()

            membership = OrganizationMember(
                organization_id=org_a.id,
                user_id=viewer_user.id,
                role_id=viewer_role.id,
            )
            session.add(membership)
            await session.commit()

            token_a_viewer = create_access_token(
                user_id=viewer_user.id,
                extra_claims={
                    "org_id": str(org_a.id),
                    "role": ROLE_VIEWER,
                    "email": viewer_user.email,
                },
            )

        headers_a_admin = {"Authorization": f"Bearer {token_a_admin}"}
        headers_b_admin = {"Authorization": f"Bearer {token_b_admin}"}
        headers_a_viewer = {"Authorization": f"Bearer {token_a_viewer}"}

        # 1. Org A Admin creates dataset
        resp_a = await client.post(
            "/api/v1/evaluation/datasets",
            json={"name": "Org A Dataset", "language": "en"},
            headers=headers_a_admin,
        )
        assert resp_a.status_code == 201
        dataset_a_id = resp_a.json()["id"]

        # 2. Org B cannot access Org A's dataset cases (Tenant Isolation)
        resp_b = await client.get(
            f"/api/v1/evaluation/datasets/{dataset_a_id}/cases",
            headers=headers_b_admin,
        )
        assert resp_b.status_code in (403, 404)

        # 3. Viewer in Org A can read datasets
        resp_viewer_get = await client.get(
            "/api/v1/evaluation/datasets",
            headers=headers_a_viewer,
        )
        assert resp_viewer_get.status_code == 200

        # 4. Viewer cannot create datasets (RBAC: evaluation.create forbidden)
        resp_viewer_create = await client.post(
            "/api/v1/evaluation/datasets",
            json={"name": "Viewer Dataset Attempt"},
            headers=headers_a_viewer,
        )
        assert resp_viewer_create.status_code == 403

        # 5. Viewer cannot trigger benchmark runs (RBAC: evaluation.run forbidden)
        resp_viewer_run = await client.post(
            "/api/v1/evaluation/runs",
            json={"dataset_id": dataset_a_id},
            headers=headers_a_viewer,
        )
        assert resp_viewer_run.status_code == 403

    @pytest.mark.asyncio
    async def test_audit_trail_logging(self, test_env: dict[str, Any]) -> None:
        """Confirm that all evaluation operations persist structured audit log entries."""
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            org, _, token = await self._setup_org_and_user(session, ROLE_ADMIN)

        headers = {"Authorization": f"Bearer {token}"}

        # Create dataset and case
        ds_resp = await client.post(
            "/api/v1/evaluation/datasets",
            json={"name": "Audit Test Suite", "language": "en"},
            headers=headers,
        )
        dataset_id = ds_resp.json()["id"]

        await client.post(
            f"/api/v1/evaluation/datasets/{dataset_id}/cases",
            json={"query": "What is revenue?", "route_expected": "sql"},
            headers=headers,
        )

        # Inspect audit logs in database
        async with session_factory() as session:
            stmt = (
                select(AuditLog)
                .where(
                    AuditLog.organization_id == org.id,
                    AuditLog.action.like("evaluation.%"),
                )
                .order_by(AuditLog.created_at.asc())
            )
            res = await session.execute(stmt)
            logs = list(res.scalars().all())

            actions = [log.action for log in logs]
            assert "evaluation.dataset_created" in actions
            assert "evaluation.case_created" in actions
