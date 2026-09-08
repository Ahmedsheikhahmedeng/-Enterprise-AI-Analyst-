"""Configuration settings and thresholds for Enterprise Observability & Monitoring."""

from dataclasses import dataclass, field
from functools import lru_cache


@dataclass(frozen=True)
class ObservabilityConfig:
    """Operational monitoring thresholds, sampling rules, and metric bucket specifications."""

    # Latency & performance thresholds
    slow_request_threshold_ms: float = 2000.0
    slow_sql_threshold_ms: float = 1000.0
    slow_rag_threshold_ms: float = 2500.0

    # Tracing & Sampling
    trace_sample_rate: float = 1.0  # 1.0 = 100% sampling, 0.1 = 10%
    enable_error_always_sampling: bool = True  # Always trace failing operations
    max_spans_per_trace: int = 200

    # Histogram latency buckets (milliseconds)
    latency_buckets: list[float] = field(
        default_factory=lambda: [
            10.0,
            25.0,
            50.0,
            100.0,
            250.0,
            500.0,
            1000.0,
            2500.0,
            5000.0,
            10000.0,
            30000.0,
        ]
    )

    # In-memory circular buffer retention
    max_events_buffer: int = 1000
    retention_days: int = 30

    # Redaction configuration
    sensitive_keys: tuple[str, ...] = (
        "authorization",
        "proxy-authorization",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "dsn",
        "private_key",
    )


@lru_cache(maxsize=1)
def get_observability_config() -> ObservabilityConfig:
    """Singleton getter for ObservabilityConfig."""
    return ObservabilityConfig()
