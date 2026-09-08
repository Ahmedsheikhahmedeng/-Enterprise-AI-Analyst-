"""Integration tests executing chaos scenarios via ChaosScenarioExecutor and API endpoints."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

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
from app.reliability.enums import ReliabilityRunStatus
from app.reliability.executor import ChaosScenarioExecutor
from app.reliability.scenarios import GLOBAL_SCENARIO_REGISTRY


@pytest.mark.asyncio
async def test_chaos_scenario_executor_postgres_outage() -> None:
    """Execute 'scen-pg-outage' through ChaosScenarioExecutor and verify full recovery."""
    scenario = GLOBAL_SCENARIO_REGISTRY.get("scen-pg-outage")
    assert scenario is not None

    result = await ChaosScenarioExecutor.execute_scenario(
        scenario,
        environment="test",
    )
    assert result["status"] == ReliabilityRunStatus.PASSED.value
    assert result["fault_type"] == "POSTGRES_UNAVAILABLE"
    assert result["mttd_seconds"] > 0
    assert result["time_to_recovery_seconds"] > 0
    assert len(result["assertions"]) >= 4

    # Verify all assertions passed
    for assertion in result["assertions"]:
        assert assertion["status"] == "PASSED"


@pytest.mark.asyncio
async def test_chaos_scenario_executor_llm_failover() -> None:
    """Execute 'scen-llm-failover' and verify retry storm protection and circuit breaker."""
    scenario = GLOBAL_SCENARIO_REGISTRY.get("scen-llm-failover")
    assert scenario is not None

    result = await ChaosScenarioExecutor.execute_scenario(
        scenario,
        environment="test",
    )
    assert result["status"] == ReliabilityRunStatus.PASSED.value
    assert result["fault_type"] == "LLM_FAILOVER"

    assertion_types = {a["assertion_type"] for a in result["assertions"]}
    assert "RETRY_STORM_PROTECTION" in assertion_types
    assert "CIRCUIT_BREAKER_ACTIVE" in assertion_types


@pytest.mark.asyncio
async def test_chaos_production_guard() -> None:
    """Verify that attempting to execute a chaos scenario in production raises PermissionError."""
    scenario = GLOBAL_SCENARIO_REGISTRY.get("scen-redis-outage")
    assert scenario is not None

    with pytest.raises(PermissionError, match="strictly prohibited in production"):
        await ChaosScenarioExecutor.execute_scenario(
            scenario,
            environment="production",
        )


@pytest.mark.asyncio
async def test_reliability_api_endpoints() -> None:
    """Verify REST API endpoints for scenarios, readiness, and report."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # Seed test user and org
    async with session_factory() as session:
        rbac_svc = RBACService()
        await rbac_svc.seed_system_rbac(session)

        uid = uuid.uuid4().hex[:8]
        org = Organization(name=f"Reliability Org {uid}", slug=f"rel-org-{uid}", is_active=True)
        session.add(org)
        await session.flush()

        user = User(
            email=f"rel_admin_{uid}@example.com",
            password_hash=hash_password("Password123!"),
            first_name="Reliability",
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

        user_id = user.id
        org_id = org.id

    token = create_access_token(
        user_id=user_id,
        extra_claims={"role": ROLE_ADMIN},
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": str(org_id),
    }

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. List scenarios
            resp = await client.get("/api/v1/reliability/scenarios", headers=headers)
            assert resp.status_code == 200
            scenarios = resp.json()
            assert len(scenarios) >= 22

            # 2. Get scenario by ID
            resp_single = await client.get(
                "/api/v1/reliability/scenarios/scen-pg-outage", headers=headers
            )
            assert resp_single.status_code == 200
            assert resp_single.json()["id"] == "scen-pg-outage"

            # 3. Trigger run (non-production)
            resp_run = await client.post(
                "/api/v1/reliability/runs",
                json={"scenario_id": "scen-pg-outage", "environment": "test"},
                headers=headers,
            )
            assert resp_run.status_code == 201
            run_data = resp_run.json()
            assert run_data["status"] == "PASSED"
            assert len(run_data["assertions"]) >= 1

            # 4. Trigger run in production should be blocked with 400
            resp_prod = await client.post(
                "/api/v1/reliability/runs",
                json={"scenario_id": "scen-pg-outage", "environment": "production"},
                headers=headers,
            )
            assert resp_prod.status_code == 400

            # 5. Production readiness
            resp_readiness = await client.get("/api/v1/reliability/readiness", headers=headers)
            assert resp_readiness.status_code == 200
            assert resp_readiness.json()["decision"] in ("READY", "READY_WITH_WARNINGS")

            # 6. Full report
            resp_report = await client.get("/api/v1/reliability/report", headers=headers)
            assert resp_report.status_code == 200
            assert resp_report.json()["total_scenarios_defined"] >= 22
    finally:
        await dispose_database_engine(engine)
