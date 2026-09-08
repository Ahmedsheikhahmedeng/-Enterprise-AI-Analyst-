"""E2E Test: Journey 1 — New Organization & Authentication Flow."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.product.journeys import CanonicalJourneysRunner
from app.product.service import ProductService


@pytest.mark.asyncio
async def test_canonical_journey_1_execution() -> None:
    result = await CanonicalJourneysRunner.run_journey_1_new_org(
        org_name="Enterprise Corp", admin_email="admin@enterprise.corp"
    )
    assert result.status == "SUCCESS"
    assert result.journey_id == "J1"
    assert len(result.steps) == 3
    assert result.evidence["tenant_bound"] is True
    assert result.evidence["rbac_enforced"] is True


@pytest.mark.asyncio
async def test_product_public_endpoints(client: AsyncClient) -> None:
    # 1. Health check endpoint
    res_health = await client.get("/api/v1/product/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["status"] in {"HEALTHY", "DEGRADED"}
    assert "components" in health_data

    # 2. Release manifest endpoint
    res_manifest = await client.get("/api/v1/product/manifest")
    assert res_manifest.status_code == 200
    manifest = res_manifest.json()
    assert manifest["product_name"] == "Enterprise AI Analyst"
    assert len(manifest["enabled_features"]) > 0


@pytest.mark.asyncio
async def test_auth_rbac_endpoint_enforcement(
    client: AsyncClient, viewer_headers: dict[str, str], db_session: AsyncSession
) -> None:
    # 1. Unauthenticated request to protected admin endpoint must be rejected
    res_unauth = await client.get("/api/v1/product/diagnostics")
    assert res_unauth.status_code in {401, 403}

    # 2. Viewer without required permissions is blocked
    res_forbidden = await client.get("/api/v1/product/diagnostics", headers=viewer_headers)
    assert res_forbidden.status_code in {401, 403}

    # 3. Direct service evaluation for authorized diagnostics
    service = ProductService(db_session)
    diag = await service.get_diagnostics()
    assert diag.version == "1.0.0-rc1"
    assert diag.features["multi_tenancy"] is True
    assert diag.features["finops_cost_governance"] is True
