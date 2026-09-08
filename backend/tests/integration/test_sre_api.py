"""Integration tests for SRE REST APIs: Dashboards, SLIs/SLOs, Alerts, Incidents, and Release Gates."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
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
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN
from app.rbac.service import RBACService


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await dispose_database_engine(engine)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await dispose_database_engine(engine)


async def _create_test_environment(
    session: AsyncSession,
) -> tuple[Organization, User, dict[str, str]]:
    rbac_svc = RBACService()
    await rbac_svc.seed_system_rbac(session)

    uid = uuid.uuid4().hex[:8]
    org = Organization(name=f"SRE Org {uid}", slug=f"sre-org-{uid}", is_active=True)
    session.add(org)
    await session.flush()

    user = User(
        email=f"sre_admin_{uid}@example.com",
        password_hash=hash_password("Password123!"),
        first_name="SRE",
        last_name="Admin",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    admin_role = (
        await session.execute(
            select(Role).where(Role.name == ROLE_ADMIN, Role.organization_id.is_(None))
        )
    ).scalar_one()

    member = OrganizationMember(organization_id=org.id, user_id=user.id, role_id=admin_role.id)
    session.add(member)
    await session.commit()

    token = create_access_token(user_id=user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)}
    return org, user, headers


@pytest.mark.asyncio
async def test_sre_dashboards_and_readiness_api(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _create_test_environment(db_session)

    # 1. Overview dashboard
    r_overview = await async_client.get("/api/v1/sre/dashboards/overview", headers=headers)
    assert r_overview.status_code == 200
    data = r_overview.json()
    assert "operational_status" in data
    assert "availability_pct" in data

    # 2. Readiness evaluation
    r_ready = await async_client.get("/api/v1/sre/readiness", headers=headers)
    assert r_ready.status_code == 200
    ready_data = r_ready.json()
    assert ready_data["status"] in ("READY", "DEGRADED", "NOT_READY")

    # 3. Dependencies matrix
    r_deps = await async_client.get("/api/v1/sre/dependencies", headers=headers)
    assert r_deps.status_code == 200
    deps_data = r_deps.json()
    assert "dependencies" in deps_data
    assert len(deps_data["dependencies"]) >= 3


@pytest.mark.asyncio
async def test_sre_sli_and_slo_crud_api(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _create_test_environment(db_session)

    # Create SLI
    sli_payload = {
        "name": "API Request Availability",
        "service": "api_gateway",
        "metric_type": "AVAILABILITY",
        "unit": "ratio",
        "enabled": True,
    }
    r_sli = await async_client.post("/api/v1/sre/slis", json=sli_payload, headers=headers)
    assert r_sli.status_code == 201
    sli = r_sli.json()
    assert sli["name"] == "API Request Availability"

    # List SLIs
    r_list = await async_client.get("/api/v1/sre/slis", headers=headers)
    assert r_list.status_code == 200
    assert any(s["id"] == sli["id"] for s in r_list.json())

    # Create SLO
    slo_payload = {
        "sli_id": sli["id"],
        "name": "99.9% API Availability",
        "service": "api_gateway",
        "target_value": 0.999,
        "window_seconds": 86400,
        "objective_type": "AVAILABILITY",
        "warning_threshold": 0.995,
        "critical_threshold": 0.990,
    }
    r_slo = await async_client.post("/api/v1/sre/slos", json=slo_payload, headers=headers)
    assert r_slo.status_code == 201
    slo = r_slo.json()
    assert slo["target_value"] == 0.999


@pytest.mark.asyncio
async def test_sre_alert_lifecycle_and_deduplication_api(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _create_test_environment(db_session)

    # Ingest Alert
    alert_payload = {
        "name": "Postgres High CPU",
        "service": "database",
        "severity": "WARNING",
        "metric": "CPU_USAGE",
        "value": 88.5,
        "threshold": 80.0,
    }
    r_alert1 = await async_client.post("/api/v1/sre/alerts", json=alert_payload, headers=headers)
    assert r_alert1.status_code == 201
    a1 = r_alert1.json()
    assert a1["count"] == 1

    # Ingest same alert -> deduplicated!
    r_alert2 = await async_client.post("/api/v1/sre/alerts", json=alert_payload, headers=headers)
    assert r_alert2.status_code == 201
    a2 = r_alert2.json()
    assert a2["id"] == a1["id"]
    assert a2["count"] == 2

    # Acknowledge
    r_ack = await async_client.post(
        f"/api/v1/sre/alerts/{a1['id']}/acknowledge",
        json={"actor": "sre-oncall", "note": "Triaging CPU spike"},
        headers=headers,
    )
    assert r_ack.status_code == 200
    assert r_ack.json()["status"] == "ACKNOWLEDGED"

    # Resolve
    r_res = await async_client.post(
        f"/api/v1/sre/alerts/{a1['id']}/resolve",
        json={"actor": "sre-oncall", "note": "Query finished"},
        headers=headers,
    )
    assert r_res.status_code == 200
    assert r_res.json()["status"] == "RESOLVED"

    # Noise ratio endpoint
    r_noise = await async_client.get("/api/v1/sre/alerts/noise", headers=headers)
    assert r_noise.status_code == 200
    assert "noise_ratio" in r_noise.json()


@pytest.mark.asyncio
async def test_sre_release_gate_and_runbook_api(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    _, _, headers = await _create_test_environment(db_session)

    # Safe runbook creation
    rb_payload = {
        "name": "Database Lock Triage",
        "service": "database",
        "trigger": "HIGH_LOCK_WAIT",
        "symptoms": ["Connections stalled"],
        "diagnostic_steps": ["SELECT count(*) FROM pg_locks"],
        "safe_actions": ["Recycle idle connections"],
    }
    r_rb = await async_client.post("/api/v1/sre/runbooks", json=rb_payload, headers=headers)
    assert r_rb.status_code == 201
    rb = r_rb.json()
    assert rb["version"] == 1

    # Destructive runbook rejected with 400 Bad Request
    bad_rb_payload = {
        "name": "Unsafe Runbook",
        "service": "database",
        "trigger": "OUTAGE",
        "symptoms": ["Critical"],
        "diagnostic_steps": ["SELECT 1"],
        "safe_actions": ["DROP TABLE critical_data"],
    }
    r_bad = await async_client.post("/api/v1/sre/runbooks", json=bad_rb_payload, headers=headers)
    assert r_bad.status_code == 400
    assert "forbidden destructive command" in r_bad.text

    # Evaluate Release Gate
    r_gate = await async_client.post(
        "/api/v1/sre/release-gates/evaluate",
        json={"service": "database"},
        headers=headers,
    )
    assert r_gate.status_code == 200
    assert r_gate.json()["decision"] == "ALLOW"
