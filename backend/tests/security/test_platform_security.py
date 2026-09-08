"""Security tests: Cross-Tenant Boundaries, CSRF, and Event Payload Sanitization — TASK 34."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.api.v1.platform.coordinator import CoordinatorRegistry
from app.api.v1.platform.dependencies import _validate_csrf
from app.api.v1.platform.sanitization import sanitize_event_payload
from app.core.exceptions import ForbiddenAppException


@pytest.mark.asyncio
async def test_coordinator_tenant_boundary_enforcement() -> None:
    """Verify that CoordinatorRegistry prevents cross-tenant hijacking of executions."""
    registry = CoordinatorRegistry()

    exec_id = uuid.uuid4()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    # Create coordinator for Org A
    coord_a = await registry.get_or_create(
        execution_id=exec_id,
        organization_id=org_a,
        user_id=user_a,
    )
    assert coord_a.organization_id == org_a

    # Org B attempts to access Org A's execution coordinator -> Must raise PermissionError
    with pytest.raises(
        PermissionError, match="Execution coordinator belongs to a different tenant"
    ):
        await registry.get_or_create(
            execution_id=exec_id,
            organization_id=org_b,
            user_id=user_b,
        )


@pytest.mark.asyncio
async def test_csrf_validation_cookie_origin_mismatch() -> None:
    """Verify CSRF validation rejects requests with untrusted Origin header."""
    mock_request = MagicMock()
    mock_request.headers = {
        "Origin": "https://malicious-attacker-site.com",
    }
    mock_request.cookies = {"access_token": "valid_cookie_token"}

    with pytest.raises(ForbiddenAppException) as exc_info:
        await _validate_csrf(mock_request)

    assert exc_info.value.code == "FORBIDDEN"
    assert "CSRF validation failed" in exc_info.value.message


@pytest.mark.asyncio
async def test_csrf_validation_token_mismatch() -> None:
    """Verify CSRF rejects request when csrf_token cookie and header do not match."""
    mock_request = MagicMock()
    mock_request.headers = {
        "Origin": "http://localhost:3000",
        "X-CSRF-Token": "tampered_token_value",
    }
    mock_request.cookies = {
        "access_token": "valid_cookie_token",
        "csrf_token": "legitimate_server_csrf_secret",
    }

    with pytest.raises(ForbiddenAppException) as exc_info:
        await _validate_csrf(mock_request)

    assert exc_info.value.code == "FORBIDDEN"
    assert "CSRF token mismatch" in exc_info.value.message


def test_no_credential_leakage_in_event_sanitization() -> None:
    """Verify raw system prompts, API keys, DSN passwords, and auth headers are completely blocked."""
    event_data = {
        "message": "Processed query successfully",
        "openai_api_key": "sk-1234567890abcdef1234567890abcdef",
        "database_url": "postgresql://postgres:p@ssword123@localhost:5432/db",
        "private_system_instructions": "System prompt: you are an internal agent...",
        "user_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "diagnostics": {
            "sql_password": "supersecretpassword",
            "safe_count": 10,
        },
    }

    sanitized = sanitize_event_payload(event_data)

    assert "openai_api_key" not in sanitized
    assert "private_system_instructions" not in sanitized
    assert "user_token" not in sanitized
    assert "sql_password" not in sanitized["diagnostics"]
    assert sanitized["diagnostics"]["safe_count"] == 10
    # Text scrub of database password
    assert "p@ssword123" not in str(sanitized.get("database_url", ""))
