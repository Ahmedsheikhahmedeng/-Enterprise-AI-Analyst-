import pytest
from httpx import AsyncClient

from app.schemas.health import HealthResponse


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client: AsyncClient) -> None:
    """Verify GET /api/v1/health responds with 200 OK and valid body structure."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "enterprise-ai-analyst"
    assert data["version"] == "0.1.0"

    # Validate against strict Pydantic model
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
