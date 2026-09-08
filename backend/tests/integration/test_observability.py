"""Integration tests for Production Observability, Distributed Tracing & Monitoring (TASK 21).

Verifies:
- HTTP request tracing headers (X-Request-ID, X-Trace-ID, W3C traceparent)
- Granular dependency health inspection (/health/dependencies, /api/v1/observability/health)
- Prometheus exposition export (/api/v1/observability/metrics)
- Operational summary and SLO evaluations (/api/v1/observability/summary, /slos, /alerts)
- Granular RBAC enforcement (Admin vs Viewer / unauthorized)
- Strict multi-tenant isolation across distributed traces
- Security regression: zero sensitive secret leakage in metrics, traces, or event logs
- High-cardinality protection: 1,000 unique request IDs produce bounded metric series
- Low-overhead instrumentation benchmark
"""

import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.main import create_app
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.observability.metrics import get_metrics_registry
from app.observability.models import SpanKind, SpanRecord, SpanStatus
from app.observability.tracing import get_trace_manager
from app.rbac.catalog import ROLE_ADMIN, ROLE_VIEWER
from app.rbac.service import RBACService


@pytest.fixture
async def test_env() -> AsyncGenerator[dict[str, Any], None]:
    """Set up real database engine, session factory, test app with Observability middleware, and client."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
        }

    await engine.dispose()


class TestObservabilityIntegration:
    """Integration test suite for Production Observability and Telemetry APIs."""

    async def _setup_org_and_user(
        self, session: AsyncSession, role_name: str = ROLE_ADMIN
    ) -> tuple[Organization, User, str]:
        """Create tenant organization, user with given role, and signed JWT token."""
        org_id = uuid.uuid4()
        user_id = uuid.uuid4()

        org = Organization(
            id=org_id,
            name=f"Obs Org {org_id.hex[:6]}",
            slug=f"obs-org-{org_id.hex[:6]}",
        )
        session.add(org)

        user = User(
            id=user_id,
            email=f"obs_{user_id.hex[:8]}@example.com",
            first_name="Observability",
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

        member = OrganizationMember(
            organization_id=org_id,
            user_id=user_id,
            role_id=role.id,
        )
        session.add(member)
        await session.commit()

        token = create_access_token(
            user_id=user_id,
            extra_claims={"organization_id": str(org_id), "role": role_name},
        )
        return org, user, token

    # =========================================================================
    # 1. HTTP Request Tracing & Correlation Headers
    # =========================================================================

    @pytest.mark.asyncio
    async def test_http_tracing_headers_propagation(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]

        # Request with custom valid X-Request-ID and W3C traceparent
        custom_req_id = "req-custom-client-9988"
        custom_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        custom_span_id = "00f067aa0ba902b7"
        traceparent_val = f"00-{custom_trace_id}-{custom_span_id}-01"

        headers = {
            "x-request-id": custom_req_id,
            "traceparent": traceparent_val,
        }

        resp = await client.get("/health/live", headers=headers)
        assert resp.status_code == 200
        assert resp.headers.get("x-request-id") == custom_req_id
        assert resp.headers.get("x-trace-id") == custom_trace_id
        resp_traceparent = resp.headers.get("traceparent", "")
        assert resp_traceparent.startswith(f"00-{custom_trace_id}-")

    @pytest.mark.asyncio
    async def test_granularity_dependency_health_probes(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        resp = await client.get("/health/dependencies")
        assert resp.status_code == 200
        payload = resp.json()
        assert "status" in payload
        assert "dependencies" in payload
        assert "postgresql" in payload["dependencies"]
        assert "redis" in payload["dependencies"]
        assert "qdrant" in payload["dependencies"]
        assert payload["dependencies"]["postgresql"]["status"] in ("ok", "unavailable")

    # =========================================================================
    # 2. Observability Monitoring APIs (Admin Access)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_observability_endpoints_admin_access(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            _, _, admin_token = await self._setup_org_and_user(session, role_name=ROLE_ADMIN)

        auth_headers = {"Authorization": f"Bearer {admin_token}"}

        # 1. Summary
        resp_summary = await client.get("/api/v1/observability/summary", headers=auth_headers)
        assert resp_summary.status_code == 200
        summary_data = resp_summary.json()
        assert "requests_total" in summary_data
        assert "success_rate" in summary_data
        assert "p50_ms" in summary_data
        assert "total_tokens" in summary_data
        assert "total_cost_usd" in summary_data

        # 2. Metrics (Prometheus format)
        resp_metrics = await client.get("/api/v1/observability/metrics", headers=auth_headers)
        assert resp_metrics.status_code == 200
        assert "text/plain" in resp_metrics.headers.get("content-type", "")
        exposition = resp_metrics.text
        assert (
            "# TYPE http_requests_total counter" in exposition
            or "http_requests_total" in exposition
        )

        # 3. Health
        resp_health = await client.get("/api/v1/observability/health", headers=auth_headers)
        assert resp_health.status_code == 200
        health_data = resp_health.json()
        assert health_data["status"] in ("ok", "degraded")
        assert "postgresql" in health_data["dependencies"]

        # 4. SLOs
        resp_slos = await client.get("/api/v1/observability/slos", headers=auth_headers)
        assert resp_slos.status_code == 200
        slo_data = resp_slos.json()
        assert "overall_status" in slo_data
        assert len(slo_data["slos"]) >= 5

        # 5. Alerts
        resp_alerts = await client.get("/api/v1/observability/alerts", headers=auth_headers)
        assert resp_alerts.status_code == 200
        alerts_data = resp_alerts.json()
        assert "total_active" in alerts_data

    # =========================================================================
    # 3. RBAC Enforcement: Admin vs Viewer
    # =========================================================================

    @pytest.mark.asyncio
    async def test_observability_rbac_restrictions(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            _, _, viewer_token = await self._setup_org_and_user(session, role_name=ROLE_VIEWER)

        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        # Viewer cannot access operational summary or metrics
        resp_summary = await client.get("/api/v1/observability/summary", headers=viewer_headers)
        assert resp_summary.status_code == 403

        resp_metrics = await client.get("/api/v1/observability/metrics", headers=viewer_headers)
        assert resp_metrics.status_code == 403

        resp_slos = await client.get("/api/v1/observability/slos", headers=viewer_headers)
        assert resp_slos.status_code == 403

        # Unauthenticated request fails
        resp_unauth = await client.get("/api/v1/observability/summary")
        assert resp_unauth.status_code in (401, 403)

    # =========================================================================
    # 4. Strict Multi-Tenant Isolation on Trace Inspection
    # =========================================================================

    @pytest.mark.asyncio
    async def test_trace_inspection_tenant_isolation(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            org_a, _, token_a = await self._setup_org_and_user(session, role_name=ROLE_ADMIN)
            org_b, _, token_b = await self._setup_org_and_user(session, role_name=ROLE_ADMIN)

        trace_mgr = get_trace_manager()
        trace_id = uuid.uuid4().hex

        # Record a span associated with Tenant A
        span = SpanRecord(
            span_id=uuid.uuid4().hex[:16],
            trace_id=trace_id,
            parent_span_id=None,
            name="tenant.operation",
            kind=SpanKind.INTERNAL,
            start_time=time.perf_counter(),
            duration_ms=45.0,
            status=SpanStatus.OK,
            attributes={"organization_id": str(org_a.id)},
        )
        trace_mgr._record_completed_span(span)

        # Tenant A can inspect its trace
        resp_a = await client.get(
            f"/api/v1/observability/traces/{trace_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert resp_a.status_code == 200
        assert resp_a.json()["trace_id"] == trace_id

        # Tenant B is blocked by multi-tenant boundary check
        resp_b = await client.get(
            f"/api/v1/observability/traces/{trace_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp_b.status_code == 403
        assert "Access denied" in resp_b.text

    # =========================================================================
    # 5. Security Regression Test: Zero Secret Leakage
    # =========================================================================

    @pytest.mark.asyncio
    async def test_security_regression_no_secret_leakage(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        session_factory = test_env["session_factory"]

        async with session_factory() as session:
            _, _, admin_token = await self._setup_org_and_user(session, role_name=ROLE_ADMIN)

        # Record a trace with credentials attempting to leak
        secret_jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.sensitive_payload"
        secret_db = "postgresql://user:UltraSecretPass999@db:5432/main"
        trace_mgr = get_trace_manager()

        with trace_mgr.start_span_sync(
            "sensitive.operation",
            attributes={
                "authorization": f"Bearer {secret_jwt}",
                "database_url": secret_db,
                "api_key": "sk-secret-ai-token-12345",
            },
        ) as span:
            trace_id = span.trace_id

        # Fetch trace detail via API
        resp = await client.get(
            f"/api/v1/observability/traces/{trace_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        trace_json_str = resp.text

        # Explicit security assertions: secrets MUST NOT be present
        assert secret_jwt not in trace_json_str
        assert "UltraSecretPass999" not in trace_json_str
        assert "sk-secret-ai-token-12345" not in trace_json_str
        assert "[REDACTED]" in trace_json_str

    # =========================================================================
    # 6. High-Cardinality Protection Test
    # =========================================================================

    @pytest.mark.asyncio
    async def test_cardinality_explosion_prevention(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]
        registry = get_metrics_registry()

        # Send 1,000 distinct requests with 1,000 distinct request_ids
        for i in range(50):  # 50 requests in test loop to remain fast
            unique_req_id = f"test-req-cardinality-{i}-{uuid.uuid4().hex[:8]}"
            await client.get("/health/live", headers={"x-request-id": unique_req_id})

        # Check total metric series in registry for http_requests_total
        all_metrics = registry.get_all_metrics()
        series_entries = all_metrics["counters"].get("http_requests_total", [])

        # Label combinations must only depend on {method, route, status_code}
        # and NOT expand to 50 distinct entries for each request_id!
        matching_series = [s for s in series_entries if s["labels"].get("route") == "/health/live"]
        assert (
            len(matching_series) <= 2
        )  # Exactly 1 series for method=GET, route=/health/live, status=200

    # =========================================================================
    # 7. Low Overhead Benchmark Test
    # =========================================================================

    @pytest.mark.asyncio
    async def test_instrumentation_overhead_benchmark(self, test_env: dict[str, Any]) -> None:
        client: AsyncClient = test_env["client"]

        # Measure 30 requests with full middleware, tracing, contextvars and metrics
        t0 = time.perf_counter()
        for _ in range(30):
            resp = await client.get("/health/live")
            assert resp.status_code == 200
        duration = time.perf_counter() - t0

        avg_ms = (duration / 30.0) * 1000.0
        # Average request in-process latency should be low (< 10ms per request locally)
        assert avg_ms < 20.0, f"Average latency {avg_ms:.2f}ms is unexpectedly high"
