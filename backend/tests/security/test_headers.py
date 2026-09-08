"""Security Headers & CORS Tests — TASK 22.

Verifies:
- Injection of nosniff, frame options, referrer policy, CSP, permissions policy
- CORS origin validation rejecting '*' with credentials
- Rejection of 'null' origin
"""

import pytest
from fastapi import FastAPI
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from app.security.config import SecurityConfig
from app.security.cors import validate_cors_origins
from app.security.exceptions import SecurityPolicyViolationError
from app.security.headers import SecurityHeadersMiddleware


def test_security_headers_middleware_injected() -> None:
    app = FastAPI()
    app.add_middleware(
        SecurityHeadersMiddleware, config=SecurityConfig(enable_hsts=True, hsts_force=True)
    )

    @app.get("/ping")
    def ping() -> PlainTextResponse:
        return PlainTextResponse("pong")

    client = TestClient(app)
    response = client.get("/ping")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]
    assert "Strict-Transport-Security" in response.headers


def test_cors_wildcard_with_credentials_prohibited() -> None:
    with pytest.raises(SecurityPolicyViolationError) as exc:
        validate_cors_origins(["*"], allow_credentials=True)
    assert "Wildcard '*' origin is prohibited when allow_credentials=True" in str(exc.value)


def test_cors_null_origin_prohibited() -> None:
    with pytest.raises(SecurityPolicyViolationError) as exc:
        validate_cors_origins(["null"], allow_credentials=False)
    assert "'null' origin is prohibited" in str(exc.value)


def test_cors_valid_origins_accepted() -> None:
    valid = ["https://app.example.com", "http://localhost:3000"]
    result = validate_cors_origins(valid, allow_credentials=True)
    assert result == valid
