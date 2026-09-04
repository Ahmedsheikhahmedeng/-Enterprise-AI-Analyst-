from collections.abc import AsyncIterator

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.exceptions import (
    ForbiddenAppException,
    NotFoundAppException,
    UnauthorizedAppException,
    ValidationAppException,
)
from app.main import create_app


class SamplePayload(BaseModel):
    name: str
    count: int


@pytest.fixture
async def app_with_test_routes() -> AsyncIterator[AsyncClient]:
    """Create test client with routes specifically configured to trigger errors."""
    app = create_app()
    test_router = APIRouter(prefix="/test-errors")

    @test_router.get("/not-found")
    async def trigger_not_found() -> None:
        raise NotFoundAppException(message="Custom document not found", code="DOCUMENT_NOT_FOUND")

    @test_router.get("/validation-app-error")
    async def trigger_val_app_error() -> None:
        raise ValidationAppException(message="Invalid document format", details={"field": "format"})

    @test_router.get("/unauthorized")
    async def trigger_unauthorized() -> None:
        raise UnauthorizedAppException()

    @test_router.get("/forbidden")
    async def trigger_forbidden() -> None:
        raise ForbiddenAppException()

    @test_router.post("/payload-validation")
    async def trigger_request_validation(payload: SamplePayload) -> dict[str, str]:
        return {"status": "ok"}

    @test_router.get("/unexpected")
    async def trigger_unexpected() -> None:
        raise RuntimeError("Database connection suddenly dropped with secret key db_secret_123")

    app.include_router(test_router)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_not_found_app_exception(app_with_test_routes: AsyncClient) -> None:
    """Verify NotFoundAppException maps to 404 with structured error envelope."""
    res = await app_with_test_routes.get("/test-errors/not-found")
    assert res.status_code == 404
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] == "DOCUMENT_NOT_FOUND"
    assert body["error"]["message"] == "Custom document not found"
    assert "request_id" in body["error"]


@pytest.mark.asyncio
async def test_validation_app_exception(app_with_test_routes: AsyncClient) -> None:
    """Verify ValidationAppException maps to 422 with details."""
    res = await app_with_test_routes.get("/test-errors/validation-app-error")
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {"field": "format"}


@pytest.mark.asyncio
async def test_unauthorized_app_exception(app_with_test_routes: AsyncClient) -> None:
    """Verify UnauthorizedAppException maps to 401."""
    res = await app_with_test_routes.get("/test-errors/unauthorized")
    assert res.status_code == 401
    body = res.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_forbidden_app_exception(app_with_test_routes: AsyncClient) -> None:
    """Verify ForbiddenAppException maps to 403."""
    res = await app_with_test_routes.get("/test-errors/forbidden")
    assert res.status_code == 403
    body = res.json()
    assert body["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_request_validation_error_handler(app_with_test_routes: AsyncClient) -> None:
    """Verify FastAPI RequestValidationError maps to standardized error contract."""
    res = await app_with_test_routes.post("/test-errors/payload-validation", json={"name": "test"})
    assert res.status_code == 422
    body = res.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "validation_errors" in body["error"]["details"]


@pytest.mark.asyncio
async def test_unhandled_exception_does_not_leak_stack_trace(
    app_with_test_routes: AsyncClient,
) -> None:
    """Verify unexpected 500 error returns safe envelope and does not leak secrets."""
    res = await app_with_test_routes.get("/test-errors/unexpected")
    assert res.status_code == 500
    body = res.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "An unexpected error occurred" in body["error"]["message"]
    assert "db_secret_123" not in res.text
    assert "RuntimeError" not in res.text
    assert "request_id" in body["error"]


@pytest.mark.asyncio
async def test_unrouted_path_returns_standard_error_envelope(
    client: AsyncClient,
) -> None:
    """Verify unrouted 404 adheres to standard API error envelope."""
    res = await client.get("/api/v1/non-existent-endpoint")
    assert res.status_code == 404
    body = res.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body["error"]
