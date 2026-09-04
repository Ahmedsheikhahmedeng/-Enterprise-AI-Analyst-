import re
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.exceptions import unhandled_exception_handler
from app.core.logging import get_logger, request_id_ctx_var, trace_id_ctx_var

logger = get_logger("middleware.correlation")

CORRELATION_ID_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
HEADER_REQUEST_ID = "X-Request-ID"
HEADER_TRACE_ID = "X-Trace-ID"


def _sanitize_id(raw_id: str | None) -> str:
    """Validate and sanitize an incoming ID; fallback to fresh UUID4 if malformed."""
    if raw_id and CORRELATION_ID_REGEX.match(raw_id):
        return raw_id
    return uuid.uuid4().hex


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware ensuring every HTTP request carries validated request_id and trace_id."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Resolve or generate correlation IDs
        raw_req_id = request.headers.get(HEADER_REQUEST_ID)
        raw_trace_id = request.headers.get(HEADER_TRACE_ID)

        request_id = _sanitize_id(raw_req_id)
        trace_id = _sanitize_id(raw_trace_id)

        # Store in request state for endpoint/dependency consumption
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        # Bind to async context variables for structlog
        token_req = request_id_ctx_var.set(request_id)
        token_trace = trace_id_ctx_var.set(trace_id)

        start_time = time.perf_counter()

        logger.info(
            "HTTP request started",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        try:
            response: Response = await call_next(request)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

            response.headers[HEADER_REQUEST_ID] = request_id
            response.headers[HEADER_TRACE_ID] = trace_id

            logger.info(
                "HTTP request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=elapsed_ms,
            )
            return response
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                "HTTP request failed with unhandled exception",
                method=request.method,
                path=request.url.path,
                duration_ms=elapsed_ms,
                error=str(exc),
            )
            err_response: Response = await unhandled_exception_handler(request, exc)
            err_response.headers[HEADER_REQUEST_ID] = request_id
            err_response.headers[HEADER_TRACE_ID] = trace_id
            return err_response
        finally:
            # Reset contextvars to prevent leaks across coroutine re-use
            request_id_ctx_var.reset(token_req)
            trace_id_ctx_var.reset(token_trace)
