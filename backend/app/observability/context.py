"""Immutable request observability context and async ContextVar propagation."""

import re
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

# Regex for validating hex trace identifiers and correlation strings
SAFE_ID_REGEX = re.compile(r"^[A-Za-z0-9_\-\.]{1,64}$")
W3C_TRACEPARENT_REGEX = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")

# Async ContextVar holding current request observability context
_observability_context_var: ContextVar["ObservabilityContext | None"] = ContextVar(
    "observability_context", default=None
)


def generate_trace_id() -> str:
    """Generate a standard 128-bit (32-hex-character) distributed trace identifier."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a standard 64-bit (16-hex-character) span identifier."""
    return uuid.uuid4().hex[:16]


def sanitize_correlation_id(raw_id: str | None, max_length: int = 64) -> str:
    """Validate and sanitize an incoming correlation ID; generate clean UUID4 on failure."""
    if raw_id:
        clean = raw_id.strip()
        if 1 <= len(clean) <= max_length and SAFE_ID_REGEX.match(clean):
            return clean
    return uuid.uuid4().hex


def parse_w3c_traceparent(header_val: str | None) -> tuple[str, str, bool] | None:
    """Parse a W3C traceparent header (e.g. '00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01').

    Returns (trace_id, parent_span_id, is_sampled) or None if invalid.
    """
    if not header_val:
        return None
    match = W3C_TRACEPARENT_REGEX.match(header_val.strip())
    if not match:
        return None
    trace_id, parent_span_id, flags = match.groups()
    is_sampled = (int(flags, 16) & 0x01) == 0x01
    return trace_id, parent_span_id, is_sampled


def format_w3c_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Format standard W3C traceparent header string."""
    flags = "01" if sampled else "00"
    padded_trace = trace_id.rjust(32, "0")[-32:]
    padded_span = span_id.rjust(16, "0")[-16:]
    return f"00-{padded_trace}-{padded_span}-{flags}"


@dataclass(frozen=True)
class ObservabilityContext:
    """Immutable request execution context propagating correlation across service layers."""

    request_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    organization_id: UUID | None = None
    user_id: UUID | None = None
    route: str | None = None
    http_method: str | None = None
    started_at: datetime = datetime.now(UTC)
    is_sampled: bool = True

    def with_span(self, new_span_id: str, is_sampled: bool | None = None) -> "ObservabilityContext":
        """Derive child context maintaining parent linkage."""
        return ObservabilityContext(
            request_id=self.request_id,
            trace_id=self.trace_id,
            span_id=new_span_id,
            parent_span_id=self.span_id,
            organization_id=self.organization_id,
            user_id=self.user_id,
            route=self.route,
            http_method=self.http_method,
            started_at=self.started_at,
            is_sampled=self.is_sampled if is_sampled is None else is_sampled,
        )

    def with_tenant(
        self, organization_id: UUID, user_id: UUID | None = None
    ) -> "ObservabilityContext":
        """Enrich context with authenticated tenant identity."""
        return ObservabilityContext(
            request_id=self.request_id,
            trace_id=self.trace_id,
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            organization_id=organization_id,
            user_id=user_id or self.user_id,
            route=self.route,
            http_method=self.http_method,
            started_at=self.started_at,
            is_sampled=self.is_sampled,
        )


def get_current_context() -> ObservabilityContext | None:
    """Retrieve active ObservabilityContext from current async execution frame."""
    return _observability_context_var.get()


def bind_observability_context(
    context: ObservabilityContext | None,
) -> Token["ObservabilityContext | None"]:
    """Bind an ObservabilityContext to the current async contextvar frame."""
    return _observability_context_var.set(context)


def reset_observability_context(token: Token["ObservabilityContext | None"]) -> None:
    """Reset contextvar token preventing leakages across pooled tasks."""
    _observability_context_var.reset(token)
