"""Security Response Headers & ASGI Middleware — TASK 22.

Attaches defense-in-depth HTTP security headers to every response:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy
- Content-Security-Policy
- Strict-Transport-Security (HSTS, configurable)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.security.config import SecurityConfig


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """ASGI Middleware to inject security headers and enforce request envelope boundaries."""

    def __init__(self, app: object, config: SecurityConfig | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._config = config or SecurityConfig()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Check Content-Length if provided to reject early request bombs
        content_length = request.headers.get("content-length")
        if (
            content_length
            and content_length.isdigit()
            and int(content_length) > self._config.max_request_body_size_bytes
        ):
            from starlette.responses import JSONResponse

            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Request entity too large. Maximum allowed size is {self._config.max_request_body_size_bytes} bytes."
                },
            )

        response: Response = await call_next(request)

        # 1. Content Type Options
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Frame Options (Clickjacking protection)
        response.headers["X-Frame-Options"] = "DENY"

        # 3. Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 4. Content Security Policy (restrictive for API endpoints)
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none';"
            )

        # 5. Permissions Policy
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # 6. HSTS (only on HTTPS or when explicitly forced by config)
        if self._config.enable_hsts and (request.url.scheme == "https" or self._config.hsts_force):
            hsts_val = f"max-age={self._config.hsts_max_age_seconds}"
            if self._config.hsts_include_subdomains:
                hsts_val += "; includeSubDomains"
            response.headers["Strict-Transport-Security"] = hsts_val

        return response
