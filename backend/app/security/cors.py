"""CORS Hardening Module — TASK 22.

Enforces CORS security best practices:
- Rejects wildcard '*' when allow_credentials=True
- Validates origin schemes (http/https only)
- Prevents null origin acceptance
- Provides safe CORS middleware configuration
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.security.config import SecurityConfig
from app.security.exceptions import SecurityPolicyViolationError


def validate_cors_origins(origins: list[str], allow_credentials: bool = True) -> list[str]:
    """Validate CORS origins list and ensure compliance with credentialed policies."""
    validated: list[str] = []

    for raw_origin in origins:
        origin = raw_origin.strip()
        if not origin:
            continue

        if origin == "*":
            if allow_credentials:
                raise SecurityPolicyViolationError(
                    "CORS misconfiguration: Wildcard '*' origin is prohibited when allow_credentials=True."
                )
            validated.append("*")
            continue

        if origin.lower() == "null":
            raise SecurityPolicyViolationError(
                "CORS misconfiguration: 'null' origin is prohibited."
            )

        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise SecurityPolicyViolationError(
                f"CORS misconfiguration: Invalid origin URL format: '{origin}'"
            )

        validated.append(origin)

    return validated


def get_hardened_cors_kwargs(
    allowed_origins: list[str],
    allow_credentials: bool = True,
    config: SecurityConfig | None = None,
) -> dict[str, Any]:
    """Return dictionary of hardened arguments for FastAPI/Starlette CORSMiddleware."""
    valid_origins = validate_cors_origins(allowed_origins, allow_credentials=allow_credentials)

    return {
        "allow_origins": valid_origins,
        "allow_credentials": allow_credentials,
        "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        "allow_headers": [
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
            "X-Request-ID",
            "X-Trace-ID",
            "Idempotency-Key",
            "traceparent",
        ],
        "expose_headers": [
            "X-Request-ID",
            "X-Trace-ID",
            "traceparent",
            "Retry-After",
        ],
        "max_age": 600,
    }
