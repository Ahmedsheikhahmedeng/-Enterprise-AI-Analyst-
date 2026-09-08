"""Security context propagating authenticated client identity, IP, and threat flags."""

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

_security_context_var: ContextVar["SecurityContext | None"] = ContextVar(
    "security_context", default=None
)


@dataclass(frozen=True)
class SecurityContext:
    """Immutable per-request security context tracking authorization boundaries."""

    request_id: str = "default_req"
    client_ip: str | None = None
    user_id: UUID | str | None = None
    organization_id: UUID | str | None = None
    role: str | None = None
    roles: list[str] | None = None
    is_authenticated: bool = False
    rate_limit_exempt: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


def get_security_context() -> SecurityContext | None:
    """Retrieve current security context from async ContextVar."""
    return _security_context_var.get()


def bind_security_context(context: SecurityContext) -> Token[SecurityContext | None]:
    """Bind a new security context to active async task context."""
    return _security_context_var.set(context)


def set_security_context(context: SecurityContext) -> Token[SecurityContext | None]:
    """Alias for bind_security_context."""
    return _security_context_var.set(context)


def reset_security_context(token: Token[SecurityContext | None]) -> None:
    """Reset security context variable to previous state."""
    _security_context_var.reset(token)


def clear_security_context() -> None:
    """Clear active security context."""
    _security_context_var.set(None)
