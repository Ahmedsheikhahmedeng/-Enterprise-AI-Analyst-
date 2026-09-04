import pytest
from fastapi import FastAPI

from app.main import app, create_app, lifespan


def test_app_instance() -> None:
    """Verify default application instance is created with expected metadata."""
    assert isinstance(app, FastAPI)
    assert app.title == "Enterprise AI Analyst API"
    assert app.version == "0.1.0"


def test_create_app_factory() -> None:
    """Verify application factory returns a freshly configured FastAPI instance."""
    new_app = create_app()
    assert isinstance(new_app, FastAPI)
    assert new_app.openapi_url == "/api/v1/openapi.json"
    assert new_app.docs_url == "/api/v1/docs"


@pytest.mark.asyncio
async def test_lifespan_context() -> None:
    """Verify lifespan startup and shutdown hooks execute cleanly."""
    test_app = create_app()
    async with lifespan(test_app):
        # Application is active inside context
        assert test_app.state is not None
