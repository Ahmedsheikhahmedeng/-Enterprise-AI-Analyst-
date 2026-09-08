"""Telemetry event stream manager for discrete alerts, slow requests, and exceptions."""

from collections import deque
from threading import Lock
from typing import Any

from app.observability.config import ObservabilityConfig, get_observability_config
from app.observability.context import get_current_context
from app.observability.models import TelemetryEvent
from app.observability.redaction import TelemetryRedactor


class EventManager:
    """Bounded, thread-safe in-memory circular buffer for platform telemetry events."""

    def __init__(
        self,
        config: ObservabilityConfig | None = None,
        redactor: TelemetryRedactor | None = None,
    ) -> None:
        self.config = config or get_observability_config()
        self.redactor = redactor or TelemetryRedactor(self.config)
        self._lock = Lock()
        self._buffer: deque[TelemetryEvent] = deque(maxlen=self.config.max_events_buffer)

    def record_event(
        self,
        event_name: str,
        severity: str = "INFO",
        duration_ms: float | None = None,
        attributes: dict[str, Any] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        request_id: str | None = None,
        organization_id: str | None = None,
    ) -> TelemetryEvent:
        """Create and buffer a sanitized operational telemetry event."""
        ctx = get_current_context()
        t_id = trace_id or (ctx.trace_id if ctx else "")
        s_id = span_id or (ctx.span_id if ctx else None)
        r_id = request_id or (ctx.request_id if ctx else None)
        o_id = organization_id or (
            str(ctx.organization_id) if ctx and ctx.organization_id else None
        )

        clean_attrs = self.redactor.redact_data(attributes or {})

        event = TelemetryEvent(
            trace_id=t_id,
            span_id=s_id,
            request_id=r_id,
            organization_id=o_id,
            event_name=event_name,
            severity=severity.upper(),
            duration_ms=duration_ms,
            attributes=clean_attrs,
        )

        with self._lock:
            self._buffer.append(event)

        return event

    def get_events(
        self,
        event_name: str | None = None,
        severity: str | None = None,
        trace_id: str | None = None,
        limit: int = 100,
    ) -> list[TelemetryEvent]:
        """Query buffered telemetry events with optional filtering."""
        with self._lock:
            events = list(self._buffer)

        filtered = events
        if event_name:
            filtered = [e for e in filtered if e.event_name == event_name]
        if severity:
            filtered = [e for e in filtered if e.severity == severity.upper()]
        if trace_id:
            filtered = [e for e in filtered if e.trace_id == trace_id]

        return filtered[-limit:]

    def clear(self) -> None:
        """Clear all events (used in tests)."""
        with self._lock:
            self._buffer.clear()


# Global singleton EventManager
_global_event_manager: EventManager | None = None


def get_event_manager() -> EventManager:
    """Singleton getter for EventManager."""
    global _global_event_manager
    if _global_event_manager is None:
        _global_event_manager = EventManager()
    return _global_event_manager
