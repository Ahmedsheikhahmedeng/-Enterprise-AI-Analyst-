"""FastAPI/Starlette middleware binding ObservabilityContext, request tracing, and telemetry metrics."""

import time
from collections.abc import Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.config import ObservabilityConfig, get_observability_config
from app.observability.context import (
    ObservabilityContext,
    bind_observability_context,
    format_w3c_traceparent,
    generate_span_id,
    generate_trace_id,
    parse_w3c_traceparent,
    reset_observability_context,
    sanitize_correlation_id,
)
from app.observability.events import get_event_manager
from app.observability.instrumentation.http import get_http_instrumentation
from app.observability.tracing import get_trace_manager


def _normalize_route(request: Request) -> str:
    """Extract matched path template to prevent high cardinality from path parameter values."""
    if hasattr(request, "scope") and "endpoint" in request.scope:
        # Check if route template is available
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            return str(route.path)
    path = request.url.path
    # Basic normalization for common UUID patterns in raw paths
    parts = path.strip("/").split("/")
    clean_parts: list[str] = []
    for part in parts:
        if (
            len(part) == 36
            and part.count("-") == 4
            or len(part) == 32
            and all(c in "0123456789abcdefABCDEF" for c in part)
        ):
            clean_parts.append("{id}")
        else:
            clean_parts.append(part)
    return "/" + "/".join(clean_parts) if clean_parts else "/"


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Intercepts HTTP requests to inject correlation headers, trace contexts, and metrics."""

    def __init__(self, app: Any, config: ObservabilityConfig | None = None) -> None:
        super().__init__(app)
        self.config = config or get_observability_config()
        self.http_instrumentation = get_http_instrumentation()
        self.event_manager = get_event_manager()
        self.trace_manager = get_trace_manager()

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        # 1. Resolve Request ID
        raw_req_id = request.headers.get("x-request-id")
        request_id = sanitize_correlation_id(raw_req_id)

        # 2. Resolve Distributed Trace Context
        raw_traceparent = request.headers.get("traceparent")
        parsed_traceparent = parse_w3c_traceparent(raw_traceparent) if raw_traceparent else None

        parent_span_id: str | None = None
        is_sampled: bool = True

        if parsed_traceparent:
            trace_id, parent_span_id, is_sampled = parsed_traceparent
        else:
            raw_trace_id = request.headers.get("x-trace-id")
            trace_id = (
                sanitize_correlation_id(raw_trace_id) if raw_trace_id else generate_trace_id()
            )

        span_id = generate_span_id()
        route_name = _normalize_route(request)
        method = request.method.upper()

        # 3. Create immutable Context and bind to ContextVar
        ctx = ObservabilityContext(
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            route=route_name,
            http_method=method,
            is_sampled=is_sampled,
        )
        token = bind_observability_context(ctx)

        # 4. Telemetry tracking
        self.http_instrumentation.record_request_start(method=method, route=route_name)
        start_perf = time.perf_counter()
        status_code = 500
        response: Response | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            duration_ms = max(0.0, (time.perf_counter() - start_perf) * 1000.0)
            self.event_manager.record_event(
                event_name="http_exception",
                severity="ERROR",
                duration_ms=duration_ms,
                attributes={
                    "exception.type": exc.__class__.__name__,
                    "route": route_name,
                    "method": method,
                },
                trace_id=trace_id,
                span_id=span_id,
                request_id=request_id,
            )
            raise
        finally:
            duration_ms = max(0.0, (time.perf_counter() - start_perf) * 1000.0)

            # Record completion metrics
            self.http_instrumentation.record_request_end(
                method=method,
                route=route_name,
                status_code=status_code,
                duration_ms=duration_ms,
            )

            # Slow request detection
            if duration_ms >= self.config.slow_request_threshold_ms:
                self.event_manager.record_event(
                    event_name="slow_request",
                    severity="WARNING",
                    duration_ms=duration_ms,
                    attributes={
                        "route": route_name,
                        "method": method,
                        "threshold_ms": self.config.slow_request_threshold_ms,
                    },
                    trace_id=trace_id,
                    span_id=span_id,
                    request_id=request_id,
                )

            # Add headers if response exists
            if response is not None:
                response.headers["x-request-id"] = request_id
                response.headers["x-trace-id"] = trace_id
                response.headers["traceparent"] = format_w3c_traceparent(
                    trace_id=trace_id, span_id=span_id, sampled=is_sampled
                )

            # Reset context
            reset_observability_context(token)
