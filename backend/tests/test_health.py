from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.schemas.health import HealthResponse, LivenessResponse, ReadinessResponse


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client: AsyncClient) -> None:
    """Verify GET /api/v1/health responds with 200 OK and valid body structure."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "enterprise-ai-analyst"
    assert data["version"] == "0.1.0"

    validated = HealthResponse.model_validate(data)
    assert validated.status == "ok"
    assert validated.service == "enterprise-ai-analyst"
    assert validated.version == "0.1.0"


@pytest.mark.asyncio
async def test_health_endpoint_has_correlation_headers(client: AsyncClient) -> None:
    """Verify health endpoint returns correlation headers."""
    response = await client.get("/api/v1/health")
    assert "x-request-id" in response.headers
    assert "x-trace-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0
    assert len(response.headers["x-trace-id"]) > 0


@pytest.mark.asyncio
async def test_liveness_endpoint_returns_200(client: AsyncClient) -> None:
    """Verify GET /api/v1/health/live responds with 200 OK and LivenessResponse."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "enterprise-ai-analyst"

    validated = LivenessResponse.model_validate(data)
    assert validated.status == "ok"


@pytest.mark.asyncio
async def test_readiness_all_healthy(client: AsyncClient) -> None:
    """Verify GET /api/v1/health/ready returns 200 OK when services are reachable."""
    with (
        patch("app.api.v1.health.check_database_connectivity", new=AsyncMock(return_value=True)),
        patch("app.api.v1.health.check_redis_connectivity", new=AsyncMock(return_value=True)),
        patch("app.api.v1.health.check_qdrant_connectivity", new=AsyncMock(return_value=True)),
    ):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "enterprise-ai-analyst"
        assert data["dependencies"] == {
            "postgresql": "ok",
            "redis": "ok",
            "qdrant": "ok",
        }

        validated = ReadinessResponse.model_validate(data)
        assert validated.status == "ok"
        assert validated.dependencies.postgresql == "ok"
        assert validated.dependencies.redis == "ok"
        assert validated.dependencies.qdrant == "ok"


@pytest.mark.asyncio
async def test_readiness_postgres_unhealthy(client: AsyncClient) -> None:
    """Verify GET /api/v1/health/ready returns 503 when PostgreSQL is down."""
    with (
        patch("app.api.v1.health.check_database_connectivity", new=AsyncMock(return_value=False)),
        patch("app.api.v1.health.check_redis_connectivity", new=AsyncMock(return_value=True)),
        patch("app.api.v1.health.check_qdrant_connectivity", new=AsyncMock(return_value=True)),
    ):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["postgresql"] == "unavailable"
        assert data["dependencies"]["redis"] == "ok"
        assert data["dependencies"]["qdrant"] == "ok"


@pytest.mark.asyncio
async def test_readiness_redis_unhealthy(client: AsyncClient) -> None:
    """Verify GET /api/v1/health/ready returns 503 when Redis is down."""
    with (
        patch("app.api.v1.health.check_database_connectivity", new=AsyncMock(return_value=True)),
        patch("app.api.v1.health.check_redis_connectivity", new=AsyncMock(return_value=False)),
        patch("app.api.v1.health.check_qdrant_connectivity", new=AsyncMock(return_value=True)),
    ):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["redis"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_qdrant_unhealthy(client: AsyncClient) -> None:
    """Verify GET /api/v1/health/ready returns 503 when Qdrant is down."""
    with (
        patch("app.api.v1.health.check_database_connectivity", new=AsyncMock(return_value=True)),
        patch("app.api.v1.health.check_redis_connectivity", new=AsyncMock(return_value=True)),
        patch("app.api.v1.health.check_qdrant_connectivity", new=AsyncMock(return_value=False)),
    ):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 503

        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["dependencies"]["qdrant"] == "unavailable"


@pytest.mark.asyncio
async def test_readiness_preserves_correlation_headers(client: AsyncClient) -> None:
    """Verify readiness probe response includes correlation headers."""
    response = await client.get(
        "/api/v1/health/ready",
        headers={"X-Request-ID": "test-req-ready-01", "X-Trace-ID": "test-trace-ready-02"},
    )
    assert response.headers["x-request-id"] == "test-req-ready-01"
    assert response.headers["x-trace-id"] == "test-trace-ready-02"
