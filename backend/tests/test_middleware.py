import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_middleware_generates_ids_when_missing(client: AsyncClient) -> None:
    """Verify middleware generates valid request_id and trace_id when headers omitted."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert "x-trace-id" in response.headers
    assert len(response.headers["x-request-id"]) > 10
    assert len(response.headers["x-trace-id"]) > 10


@pytest.mark.asyncio
async def test_middleware_preserves_valid_ids(client: AsyncClient) -> None:
    """Verify valid incoming X-Request-ID and X-Trace-ID headers are preserved."""
    headers = {
        "X-Request-ID": "custom-req-id-12345",
        "X-Trace-ID": "custom-trace-id-67890",
    }
    response = await client.get("/api/v1/health", headers=headers)
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "custom-req-id-12345"
    assert response.headers["x-trace-id"] == "custom-trace-id-67890"


@pytest.mark.asyncio
async def test_middleware_sanitizes_malformed_ids(client: AsyncClient) -> None:
    """Verify invalid or dangerous correlation headers are rejected and replaced."""
    headers = {
        "X-Request-ID": "malicious<script>alert(1)</script>",
        "X-Trace-ID": "a" * 100,  # exceeds maximum safe length of 64 chars
    }
    response = await client.get("/api/v1/health", headers=headers)
    assert response.status_code == 200
    # Must NOT equal the malformed input
    assert response.headers["x-request-id"] != headers["X-Request-ID"]
    assert response.headers["x-trace-id"] != headers["X-Trace-ID"]
    # Must be valid safe UUIDs
    assert len(response.headers["x-request-id"]) == 32
    assert len(response.headers["x-trace-id"]) == 32
