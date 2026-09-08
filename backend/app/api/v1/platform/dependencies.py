"""FastAPI Dependencies for Enterprise Platform APIs — TASK 34.

Includes:
- Request correlation (request_id, trace_id)
- Multi-tenant permission validation
- Browser cookie authentication & CSRF defense for mutating requests
- Per-user and per-org rate limiting
- Event coordinator and idempotency resolution
"""

import uuid
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.platform.coordinator import (
    CoordinatorRegistry,
    get_coordinator_registry,
)
from app.api.v1.platform.schemas.errors import (
    RateLimitedException,
)
from app.auth.jwt import decode_access_token
from app.auth.repository import AuthRepository
from app.core.config import get_settings
from app.core.exceptions import ForbiddenAppException, UnauthorizedAppException
from app.core.logging import get_logger, request_id_ctx_var, trace_id_ctx_var
from app.db.postgres import get_db_session
from app.models.user import User
from app.observability.instrumentation.platform import get_platform_instrumentation
from app.security.rate_limit import RateLimiter
from app.security.replay import IdempotencyManager
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_current_tenant

logger = get_logger("platform.dependencies")
_auth_repo = AuthRepository()


def get_correlation_ids(request: Request) -> tuple[str, str]:
    """Extract validated request_id and trace_id from request state or contextvars."""
    req_id = (
        getattr(request.state, "request_id", None) or request_id_ctx_var.get() or uuid.uuid4().hex
    )
    tr_id = getattr(request.state, "trace_id", None) or trace_id_ctx_var.get() or uuid.uuid4().hex
    return str(req_id), str(tr_id)


def get_coordinator_registry_dep() -> CoordinatorRegistry:
    """Dependency providing singleton CoordinatorRegistry."""
    return get_coordinator_registry()


def get_rate_limiter(request: Request) -> RateLimiter:
    """Dependency resolving RateLimiter instance."""
    redis_client = getattr(request.app.state, "redis_client", None)
    return RateLimiter(redis_client=redis_client)


def get_idempotency_manager(request: Request) -> IdempotencyManager:
    """Dependency resolving IdempotencyManager instance."""
    redis_client = getattr(request.app.state, "redis_client", None)
    return IdempotencyManager(redis_client=redis_client)


async def get_browser_or_bearer_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Extract authenticated user from Bearer Authorization header or HttpOnly session cookie."""
    token: str | None = None

    # 1. Bearer header check
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    # 2. Browser cookie fallback
    if not token:
        cookie_token = request.cookies.get("access_token") or request.cookies.get("session_token")
        if cookie_token:
            token = cookie_token

            # 3. Enforce CSRF protection on mutating HTTP requests when authenticating via Cookie
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                await _validate_csrf(request)

    if not token:
        raise UnauthorizedAppException(
            message="Authentication credentials were not provided.",
            code="MISSING_CREDENTIALS",
        )

    payload = decode_access_token(token)
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedAppException(message="Invalid token subject.", code="INVALID_TOKEN")

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError) as err:
        raise UnauthorizedAppException(
            message="Invalid user ID in token.", code="INVALID_TOKEN"
        ) from err

    user = await _auth_repo.get_user_by_id(session, user_id)
    if not user or not user.is_active:
        raise UnauthorizedAppException(
            message="User is disabled or does not exist.", code="INACTIVE_USER"
        )

    return user


async def _validate_csrf(request: Request) -> None:
    """Validate CSRF token header or strict Origin validation for browser cookie requests."""
    settings = get_settings()

    # Origin / Referer check
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if origin:
        from urllib.parse import urlparse

        origin_host = urlparse(origin).netloc
        allowed_hosts = [urlparse(o).netloc for o in settings.CORS_ORIGINS if o]
        if (
            origin_host
            and allowed_hosts
            and origin_host not in allowed_hosts
            and origin not in settings.CORS_ORIGINS
        ):
            logger.warning(
                "CSRF origin validation failed", origin=origin, allowed=settings.CORS_ORIGINS
            )
            raise ForbiddenAppException(
                message="CSRF validation failed: origin not permitted.",
                code="FORBIDDEN",
            )

    # CSRF Header check if cookie provides csrf token
    csrf_cookie = request.cookies.get("csrf_token")
    if csrf_cookie:
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_header or csrf_header != csrf_cookie:
            raise ForbiddenAppException(
                message="CSRF token mismatch or missing.",
                code="FORBIDDEN",
            )


def check_rate_limit(
    route: str,
    limit_per_minute: int = 60,
) -> Any:
    """FastAPI dependency factory enforcing rate limits per user and per tenant."""

    async def _rate_limit_dep(
        request: Request,
        tenant_context: Annotated[TenantContext, Depends(get_current_tenant)],
        rate_limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    ) -> None:
        key_user = f"user:{tenant_context.user_id}:{route}"
        key_org = f"org:{tenant_context.organization_id}:{route}"

        # Check user limit
        user_res = await rate_limiter.check(key_user, limit=limit_per_minute, window_seconds=60)
        if not user_res.allowed:
            get_platform_instrumentation().record_rate_limited(route)
            raise RateLimitedException(
                message=f"Rate limit exceeded for user. Retry after {user_res.retry_after}s.",
                retry_after=user_res.retry_after,
            )

        # Check org limit (e.g. 5x user limit)
        org_res = await rate_limiter.check(key_org, limit=limit_per_minute * 5, window_seconds=60)
        if not org_res.allowed:
            get_platform_instrumentation().record_rate_limited(route)
            raise RateLimitedException(
                message=f"Rate limit exceeded for organization. Retry after {org_res.retry_after}s.",
                retry_after=org_res.retry_after,
            )

    return _rate_limit_dep
