"""Distributed tracing manager, span nesting lifecycle, and sampling strategies."""

import random
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from app.observability.config import ObservabilityConfig, get_observability_config
from app.observability.context import (
    ObservabilityContext,
    bind_observability_context,
    generate_span_id,
    generate_trace_id,
    get_current_context,
    reset_observability_context,
)
from app.observability.models import SpanKind, SpanRecord, SpanStatus
from app.observability.redaction import TelemetryRedactor


class TraceSampler:
    """Configurable sampling engine balancing telemetry completeness and overhead."""

    def __init__(self, config: ObservabilityConfig | None = None) -> None:
        self.config = config or get_observability_config()
        self.sample_rate = max(0.0, min(1.0, self.config.trace_sample_rate))
        self.error_always = self.config.enable_error_always_sampling

    def should_sample(self, is_error: bool = False) -> bool:
        """Determine whether the current trace/span should be sampled."""
        if is_error and self.error_always:
            return True
        if self.sample_rate >= 1.0:
            return True
        if self.sample_rate <= 0.0:
            return False
        return random.random() < self.sample_rate


class TraceManager:
    """Coordinates distributed trace creation, span hierarchy nesting, and redaction."""

    def __init__(
        self,
        config: ObservabilityConfig | None = None,
        redactor: TelemetryRedactor | None = None,
        sampler: TraceSampler | None = None,
    ) -> None:
        self.config = config or get_observability_config()
        self.redactor = redactor or TelemetryRedactor(self.config)
        self.sampler = sampler or TraceSampler(self.config)
        self._completed_spans: dict[str, list[SpanRecord]] = defaultdict(list)

    @asynccontextmanager
    async def start_span_async(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> AsyncIterator[SpanRecord]:
        """Async context manager wrapping an execution span within active trace context."""
        ctx = get_current_context()
        trace_id = ctx.trace_id if ctx else generate_trace_id()
        parent_span_id = ctx.span_id if ctx else None
        span_id = generate_span_id()

        # Sanitize attributes
        clean_attrs = self.redactor.redact_data(attributes or {})

        span = SpanRecord(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=time.perf_counter(),
            status=SpanStatus.OK,
            attributes=clean_attrs,
        )

        # Update contextvar with child or root span
        if ctx:
            token = bind_observability_context(ctx.with_span(new_span_id=span_id))
        else:
            token = bind_observability_context(
                ObservabilityContext(
                    request_id=trace_id,
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )

        try:
            yield span
        except Exception as exc:
            span.status = SpanStatus.ERROR
            span.error_message = self.redactor.redact_text(str(exc))
            span.attributes["error.type"] = exc.__class__.__name__
            raise
        finally:
            span.end_time = time.perf_counter()
            span.duration_ms = max(0.0, (span.end_time - span.start_time) * 1000.0)
            if self.sampler.should_sample(is_error=(span.status == SpanStatus.ERROR)):
                self._record_completed_span(span)
            if token:
                reset_observability_context(token)

    @contextmanager
    def start_span_sync(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[SpanRecord]:
        """Synchronous context manager wrapping an execution span."""
        ctx = get_current_context()
        trace_id = ctx.trace_id if ctx else generate_trace_id()
        parent_span_id = ctx.span_id if ctx else None
        span_id = generate_span_id()

        clean_attrs = self.redactor.redact_data(attributes or {})

        span = SpanRecord(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=time.perf_counter(),
            status=SpanStatus.OK,
            attributes=clean_attrs,
        )

        # Update contextvar with child or root span
        if ctx:
            token = bind_observability_context(ctx.with_span(new_span_id=span_id))
        else:
            token = bind_observability_context(
                ObservabilityContext(
                    request_id=trace_id,
                    trace_id=trace_id,
                    span_id=span_id,
                )
            )

        try:
            yield span
        except Exception as exc:
            span.status = SpanStatus.ERROR
            span.error_message = self.redactor.redact_text(str(exc))
            span.attributes["error.type"] = exc.__class__.__name__
            raise
        finally:
            span.end_time = time.perf_counter()
            span.duration_ms = max(0.0, (span.end_time - span.start_time) * 1000.0)
            if self.sampler.should_sample(is_error=(span.status == SpanStatus.ERROR)):
                self._record_completed_span(span)
            if token:
                reset_observability_context(token)

    def _record_completed_span(self, span: SpanRecord) -> None:
        """Store span in circular trace buffer."""
        spans_list = self._completed_spans[span.trace_id]
        if len(spans_list) < self.config.max_spans_per_trace:
            spans_list.append(span)

    def get_trace_spans(self, trace_id: str) -> list[SpanRecord]:
        """Retrieve all recorded spans for a given trace."""
        return list(self._completed_spans.get(trace_id, []))

    def clear(self) -> None:
        """Clear recorded spans (for testing)."""
        self._completed_spans.clear()


# Global singleton TraceManager
_global_trace_manager: TraceManager | None = None


def get_trace_manager() -> TraceManager:
    """Singleton getter for TraceManager."""
    global _global_trace_manager
    if _global_trace_manager is None:
        _global_trace_manager = TraceManager()
    return _global_trace_manager
