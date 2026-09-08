"""Integration tests for Enterprise Report Generation, Versioning, RBAC, and Exports."""

import io
import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analyst.service import AIAnalystService
from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.main import create_app
from app.models.audit import AuditLog
from app.models.data_source import DataSource
from app.models.organization import Organization
from app.models.report import ReportVersion
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rag.models import Evidence, GroundedAnswer, RAGAnswerResult
from app.rag.service import RAGService
from app.rbac.catalog import ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER
from app.rbac.service import RBACService
from app.reports.exceptions import ReportAuthorizationError
from app.reports.models import ReportStatus
from app.reports.service import ReportService
from app.sql_agent.providers.deterministic import DeterministicSQLProvider
from app.sql_agent.service import SQLAgentService


@pytest.fixture
async def test_env() -> Any:
    """Set up database tables, seeds, and real singleton services."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    # Seed test sales table
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

    # Deterministic SQL Service
    from app.sql_agent.config import get_sql_agent_config

    sql_cfg = get_sql_agent_config()
    sql_provider = DeterministicSQLProvider()
    sql_service = SQLAgentService(provider=sql_provider, config=sql_cfg)
    app.state.sql_agent_service = sql_service

    # Mock RAG Service
    rag_mock = MagicMock(spec=RAGService)

    async def mock_rag_answer(
        query: str, organization_id: uuid.UUID, **kwargs: Any
    ) -> RAGAnswerResult:
        ev_id = "E1"
        doc_text = (
            "The annual report states enterprise demand was strong in Q4, "
            "with reported revenue at 100M."
        )
        return RAGAnswerResult(
            query=query,
            answer=GroundedAnswer(
                answer="Annual report states enterprise demand was strong in Q4 [E1].",
                evidence_ids=[ev_id],
                grounded=True,
                confidence=0.90,
                system_grounding_confidence=0.90,
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
                    page_number=12,
                    document_name="Annual_Report_2025.pdf",
                )
            ],
        )

    rag_mock.answer.side_effect = mock_rag_answer
    app.state.rag_service = rag_mock

    # AI Analyst Service
    from app.analyst.config import get_analyst_config

    analyst_service = AIAnalystService(
        sql_service=sql_service,
        rag_service=rag_mock,
        config=get_analyst_config(),
    )
    app.state.analyst_service = analyst_service

    # Report Service
    report_service = ReportService()
    app.state.report_service = report_service

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
            "analyst_service": analyst_service,
            "report_service": report_service,
        }

    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS sales CASCADE;"))
    await engine.dispose()


class TestReportsIntegrationPipeline:
    """End-to-end integration tests for report generation, RBAC, versioning, and export."""

    async def _setup_org_and_user(
        self, session: AsyncSession, role_name: str = ROLE_ADMIN
    ) -> tuple[Organization, User, str]:
        """Create org, user with specific role, and JWT token."""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()

        org = Organization(
            id=org_id,
            name=f"Report Org {org_id.hex[:6]}",
            slug=f"report-org-{org_id.hex[:6]}",
        )
        session.add(org)

        user = User(
            id=user_id,
            email=f"user_{user_id.hex[:8]}@example.com",
            first_name="Report",
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
        """Create a registered PostgreSQL datasource for the organization."""
        ds = DataSource(
            organization_id=org_id,
            name="Production Sales DB",
            type="postgresql",
            status="active",
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
                },
            },
        )
        session.add(ds)
        await session.commit()
        return ds

    async def test_end_to_end_analyst_to_report(self, test_env: dict[str, Any]) -> None:
        """Verify full flow: AIAnalyst ask -> AnalysisRun -> create_report_from_analysis."""
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]
        report_service: ReportService = test_env["report_service"]

        async with session_factory() as session:
            org, user, token = await self._setup_org_and_user(session, ROLE_ANALYST)
            ds = await self._setup_datasource(session, org.id, user.id)

            # 1. Execute Analyst Query
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
            assert res.analysis_run_id is not None

            # 2. Synthesize Report from AnalysisRun
            report, version_rec, doc = await report_service.create_report_from_analysis(
                session=session,
                organization_id=org.id,
                analysis_run_id=res.analysis_run_id,
                title="Q4 Revenue & Market Commentary",
                subtitle="Quarterly Executive Overview",
                user_id=user.id,
                template="executive",
            )

            assert report.id == doc.report_id
            assert report.organization_id == org.id
            assert report.title == "Q4 Revenue & Market Commentary"
            assert report.status == ReportStatus.DRAFT.value
            assert report.current_version == 1
            assert version_rec.version_number == 1
            assert len(doc.key_findings) >= 1
            assert len(doc.evidence) >= 1
            assert doc.content_hash != ""

            # 3. Verify AuditLog persisted
            audit_stmt = select(AuditLog).where(
                AuditLog.resource_id == str(report.id),
                AuditLog.action == "report.created",
            )
            audit_res = await session.execute(audit_stmt)
            audit_entry = audit_res.scalars().first()
            assert audit_entry is not None
            assert audit_entry.organization_id == org.id

    async def test_conflict_preservation_in_report(self, test_env: dict[str, Any]) -> None:
        """Verify that numerical contradictions (120M vs 100M) are carried over and rendered."""
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]
        report_service: ReportService = test_env["report_service"]

        async with session_factory() as session:
            org, user, _ = await self._setup_org_and_user(session, ROLE_ADMIN)
            ds = await self._setup_datasource(session, org.id, user.id)

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
            assert res.analysis_run_id is not None

            report, version_rec, doc = await report_service.create_report_from_analysis(
                session=session,
                organization_id=org.id,
                analysis_run_id=res.analysis_run_id,
                title="Conflict Reconciliation Report",
                user_id=user.id,
            )

            # Check conflicts preserved in domain document
            assert len(doc.conflicts) >= 1
            conflict = doc.conflicts[0]
            assert "485" in str(conflict.value_a) or "120" in str(conflict.value_a)
            assert "100" in str(conflict.value_b)

            # Check rendered Markdown contains conflict warning
            md_out = report_service.markdown_renderer.render(doc)
            assert "Data Conflicts & Discrepancies" in md_out

            # Check rendered HTML contains conflict table
            html_out = report_service.html_renderer.render(doc)
            assert "Data Discrepancies & Conflicts" in html_out

    async def test_multi_tenant_isolation(self, test_env: dict[str, Any]) -> None:
        """Verify that Organization A's reports cannot be accessed or exported by Organization B."""
        session_factory = test_env["session_factory"]
        report_service: ReportService = test_env["report_service"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            # Org A creates a report
            org_a, user_a, _ = await self._setup_org_and_user(session, ROLE_ADMIN)
            ds_a = await self._setup_datasource(session, org_a.id, user_a.id)

            res_a = await analyst_service.ask(
                query="What was total revenue in Q4?",
                organization_id=org_a.id,
                session=session,
                user_id=user_a.id,
                datasource_id=ds_a.id,
            )
            assert res_a.analysis_run_id is not None

            report_a, _, _ = await report_service.create_report_from_analysis(
                session=session,
                organization_id=org_a.id,
                analysis_run_id=res_a.analysis_run_id,
                title="Org A Financial Secrets",
            )

            # Org B tries to access Org A's report
            org_b, _, _ = await self._setup_org_and_user(session, ROLE_ADMIN)

            with pytest.raises(ReportAuthorizationError):
                await report_service.get_report(
                    session=session,
                    organization_id=org_b.id,
                    report_id=report_a.id,
                )

            with pytest.raises(ReportAuthorizationError):
                await report_service.export_report(
                    session=session,
                    organization_id=org_b.id,
                    report_id=report_a.id,
                    export_format="pdf",
                )

    async def test_publish_and_immutability_flow(self, test_env: dict[str, Any]) -> None:
        """Verify publishing a report sets published status and creates immutable history."""
        session_factory = test_env["session_factory"]
        report_service: ReportService = test_env["report_service"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            org, user, _ = await self._setup_org_and_user(session, ROLE_ADMIN)
            ds = await self._setup_datasource(session, org.id, user.id)

            res = await analyst_service.ask(
                query="What was total revenue in Q4?",
                organization_id=org.id,
                session=session,
                user_id=user.id,
                datasource_id=ds.id,
            )
            assert res.analysis_run_id is not None

            report, v1, doc = await report_service.create_report_from_analysis(
                session=session,
                organization_id=org.id,
                analysis_run_id=res.analysis_run_id,
                title="Publish Test Report",
            )
            assert report.status == ReportStatus.DRAFT.value

            # Publish
            pub_report, pub_v1, pub_doc = await report_service.publish_report(
                session=session,
                organization_id=org.id,
                report_id=report.id,
                user_id=user.id,
            )
            assert pub_report.status == ReportStatus.PUBLISHED.value
            assert pub_v1.status == ReportStatus.PUBLISHED.value
            assert pub_report.published_at is not None

            # Creating a new version after publish creates v2
            v2 = await report_service.version_manager.create_or_update_version(
                session=session,
                report=pub_report,
                doc=pub_doc,
                rendered_content="# Updated v2 content",
                user_id=user.id,
                force_new_version=True,
            )
            assert v2.version_number == 2
            assert pub_report.current_version == 2

            # Historical v1 is still published and immutable
            stmt_v1 = select(ReportVersion).where(
                ReportVersion.report_id == report.id,
                ReportVersion.version_number == 1,
            )
            r_v1 = (await session.execute(stmt_v1)).scalars().first()
            assert r_v1 is not None
            assert r_v1.status == ReportStatus.PUBLISHED.value

    async def test_rest_api_reports_lifecycle(self, test_env: dict[str, Any]) -> None:
        """Test REST API endpoints for reports lifecycle: create, get, list, publish, export."""
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]
        analyst_service: AIAnalystService = test_env["analyst_service"]

        async with session_factory() as session:
            org, user, token = await self._setup_org_and_user(session, ROLE_ANALYST)
            ds = await self._setup_datasource(session, org.id, user.id)

            res = await analyst_service.ask(
                query="What was the revenue by quarter?",
                organization_id=org.id,
                session=session,
                user_id=user.id,
                datasource_id=ds.id,
            )
            assert res.analysis_run_id is not None
            run_id = str(res.analysis_run_id)

        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create Report from Analysis
        payload = {
            "analysis_run_id": run_id,
            "title": "API Generated Financial Report",
            "subtitle": "Q4 Performance",
            "template": "executive",
        }
        create_res = await client.post(
            "/api/v1/reports/from-analysis", json=payload, headers=headers
        )
        assert create_res.status_code == 201, create_res.text
        report_data = create_res.json()
        report_id = report_data["report_id"]
        assert report_data["version"] == 1
        assert report_data["status"] == "draft"

        # 2. List Reports
        list_res = await client.get("/api/v1/reports", headers=headers)
        assert list_res.status_code == 200
        list_data = list_res.json()
        assert list_data["total"] >= 1
        assert any(r["report_id"] == report_id for r in list_data["items"])

        # 3. Get Report by ID
        get_res = await client.get(f"/api/v1/reports/{report_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["title"] == "API Generated Financial Report"

        # 4. Export Markdown
        md_res = await client.get(f"/api/v1/reports/{report_id}/export/markdown", headers=headers)
        assert md_res.status_code == 200
        assert "text/markdown" in md_res.headers["content-type"]
        assert "# API Generated Financial Report" in md_res.text

        # 5. Export HTML
        html_res = await client.get(f"/api/v1/reports/{report_id}/export/html", headers=headers)
        assert html_res.status_code == 200
        assert "text/html" in html_res.headers["content-type"]
        assert "<!DOCTYPE html>" in html_res.text

        # 6. Export PDF (and verify with pypdf)
        pdf_res = await client.get(f"/api/v1/reports/{report_id}/export/pdf", headers=headers)
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        pdf_bytes = pdf_res.content
        assert pdf_bytes.startswith(b"%PDF-")

        reader = PdfReader(io.BytesIO(pdf_bytes))
        assert len(reader.pages) >= 1
        extracted = reader.pages[0].extract_text()
        assert "API Generated Financial Report" in extracted

        # 7. Export CSV
        csv_res = await client.get(f"/api/v1/reports/{report_id}/export/csv", headers=headers)
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers["content-type"]
        assert "quarter" in csv_res.text.lower() or "revenue" in csv_res.text.lower()

        # 8. Publish
        pub_res = await client.post(f"/api/v1/reports/{report_id}/publish", headers=headers)
        assert pub_res.status_code == 200
        assert pub_res.json()["status"] == "published"

        # 9. Archive
        arch_res = await client.post(f"/api/v1/reports/{report_id}/archive", headers=headers)
        assert arch_res.status_code == 200
        assert arch_res.json()["status"] == "archived"

    async def test_rbac_viewer_restricted_actions(self, test_env: dict[str, Any]) -> None:
        """Verify that Viewer role can read reports but cannot create or publish."""
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            org, _, viewer_token = await self._setup_org_and_user(session, ROLE_VIEWER)

        headers = {"Authorization": f"Bearer {viewer_token}"}

        # Viewer tries to create report -> 403 Forbidden
        create_res = await client.post(
            "/api/v1/reports/from-analysis",
            json={"analysis_run_id": str(uuid.uuid4()), "title": "Unauthorized"},
            headers=headers,
        )
        assert create_res.status_code == 403
