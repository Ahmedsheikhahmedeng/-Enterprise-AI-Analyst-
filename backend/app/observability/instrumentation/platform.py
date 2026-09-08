"""Observability Instrumentation for Enterprise Platform, API & Streaming — TASK 34."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry

_METRIC_API_REQUESTS_TOTAL = "api_requests_total"
_METRIC_API_REQUEST_DURATION = "api_request_duration_seconds"
_METRIC_SSE_CONNECTIONS_TOTAL = "sse_connections_total"
_METRIC_SSE_ACTIVE_CONNECTIONS = "sse_active_connections"
_METRIC_SSE_DISCONNECT_TOTAL = "sse_disconnect_total"
_METRIC_SSE_REPLAY_TOTAL = "sse_replay_total"
_METRIC_SSE_BACKPRESSURE_TOTAL = "sse_backpressure_total"
_METRIC_API_ERRORS_TOTAL = "api_errors_total"
_METRIC_API_RATE_LIMITED_TOTAL = "api_rate_limited_total"

# Standard low-cardinality latency buckets in seconds
_PLATFORM_LATENCY_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]


class PlatformInstrumentation:
    """Provides structured, high-cardinality safe telemetry for Platform REST & SSE streams."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self.registry = registry or get_metrics_registry()

    def record_api_request(
        self,
        route: str,
        method: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record an incoming API request completion and its latency."""
        labels = {
            "route": route,
            "method": method.upper(),
            "status_code": str(status_code),
        }
        self.registry.increment(_METRIC_API_REQUESTS_TOTAL, 1.0, labels)
        self.registry.observe(
            _METRIC_API_REQUEST_DURATION,
            duration_seconds,
            labels,
            custom_buckets=_PLATFORM_LATENCY_BUCKETS,
        )

    def record_api_error(self, route: str, error_code: str) -> None:
        """Record an API error occurrence with canonical error code."""
        labels = {
            "route": route,
            "error_code": error_code,
        }
        self.registry.increment(_METRIC_API_ERRORS_TOTAL, 1.0, labels)

    def record_rate_limited(self, route: str) -> None:
        """Record a rate-limiting rejection event."""
        labels = {"route": route}
        self.registry.increment(_METRIC_API_RATE_LIMITED_TOTAL, 1.0, labels)

    def record_sse_connected(self) -> None:
        """Record an established SSE streaming connection."""
        self.registry.increment(_METRIC_SSE_CONNECTIONS_TOTAL, 1.0)
        self.registry.gauge(_METRIC_SSE_ACTIVE_CONNECTIONS, self._get_active_sse_count() + 1.0)

    def record_sse_disconnected(self) -> None:
        """Record a disconnected SSE streaming connection."""
        self.registry.increment(_METRIC_SSE_DISCONNECT_TOTAL, 1.0)
        current = self._get_active_sse_count()
        self.registry.gauge(_METRIC_SSE_ACTIVE_CONNECTIONS, max(0.0, current - 1.0))

    def record_sse_replay(self) -> None:
        """Record an SSE event replay request."""
        self.registry.increment(_METRIC_SSE_REPLAY_TOTAL, 1.0)

    def record_sse_backpressure(self) -> None:
        """Record an SSE subscriber queue overflow / backpressure event."""
        self.registry.increment(_METRIC_SSE_BACKPRESSURE_TOTAL, 1.0)

    def _get_active_sse_count(self) -> float:
        """Read active SSE connections gauge from registry or default to 0."""
        try:
            val = self.registry.get_gauge_value(_METRIC_SSE_ACTIVE_CONNECTIONS)
            return float(val) if val is not None else 0.0
        except Exception:
            return 0.0


_global_platform_instrumentation: PlatformInstrumentation | None = None


def get_platform_instrumentation() -> PlatformInstrumentation:
    """Singleton getter for platform instrumentation."""
    global _global_platform_instrumentation
    if _global_platform_instrumentation is None:
        _global_platform_instrumentation = PlatformInstrumentation()
    return _global_platform_instrumentation
