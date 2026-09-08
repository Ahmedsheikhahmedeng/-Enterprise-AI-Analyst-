"""HTTP request instrumentation recording throughput, latency, in-flight, and errors."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class HTTPInstrumentation:
    """Records HTTP request telemetry with bounded label dimensions."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_request_start(self, method: str, route: str) -> None:
        """Increment in-flight requests gauge."""
        clean_method = method.upper()
        # For in_flight gauge, use bounded dimensions
        self.metrics.increment(
            "http_requests_in_flight",
            value=1.0,
            labels={"method": clean_method},
            description="Current active HTTP requests in flight",
        )

    def record_request_end(
        self,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record completed HTTP request metrics."""
        clean_method = method.upper()
        clean_route = route or "/"
        str_status = str(status_code)
        labels = {
            "method": clean_method,
            "route": clean_route,
            "status_code": str_status,
        }

        # 1. Total requests
        self.metrics.increment(
            "http_requests_total",
            value=1.0,
            labels=labels,
            description="Total HTTP requests processed",
        )
        self.metrics.increment(
            "enterprise_ai_http_requests_total",
            value=1.0,
            labels=labels,
            description="Enterprise AI total HTTP requests processed",
        )

        # 2. Duration histogram
        self.metrics.observe(
            "http_request_duration_ms",
            value=duration_ms,
            labels={"method": clean_method, "route": clean_route},
            description="HTTP request processing latency in milliseconds",
        )

        # 3. In-flight decrement
        self.metrics.increment(
            "http_requests_in_flight",
            value=-1.0,
            labels={"method": clean_method},
            description="Current active HTTP requests in flight",
        )

        # 4. Error counter if 4xx or 5xx
        if status_code >= 400:
            error_labels = {
                "method": clean_method,
                "route": clean_route,
                "status_code": str_status,
            }
            self.metrics.increment(
                "http_errors_total",
                value=1.0,
                labels=error_labels,
                description="Total HTTP requests resulting in 4xx or 5xx errors",
            )


# Global singleton
_global_http_instrumentation: HTTPInstrumentation | None = None


def get_http_instrumentation() -> HTTPInstrumentation:
    """Singleton getter for HTTPInstrumentation."""
    global _global_http_instrumentation
    if _global_http_instrumentation is None:
        _global_http_instrumentation = HTTPInstrumentation()
    return _global_http_instrumentation
