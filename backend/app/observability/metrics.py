"""Central thread-safe MetricsRegistry with high-cardinality protection."""

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from threading import Lock
from typing import Any

from app.observability.config import ObservabilityConfig, get_observability_config
from app.observability.exceptions import HighCardinalityViolationError


class MetricType(StrEnum):
    """Supported telemetry metric measurement types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


# Forbidden label keys to prevent cardinality explosion in metric series
FORBIDDEN_LABEL_KEYS: frozenset[str] = frozenset(
    {
        "user_id",
        "organization_id",
        "request_id",
        "trace_id",
        "span_id",
        "query",
        "prompt",
        "response",
        "sql",
        "sql_hash",
        "document_id",
        "chunk_id",
        "job_id",
        "worker_id",
        "memory_id",
        "token",
        "secret",
        "password",
    }
)


def format_label_tuple(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    """Serialize labels into a deterministic hashable key."""
    if not labels:
        return ()
    return tuple(sorted((str(k).strip(), str(v).strip()) for k, v in labels.items()))


@dataclass
class HistogramSeries:
    """Histogram tracking observations across sorted latency/value buckets."""

    buckets: list[float]
    counts: list[int] = field(default_factory=list)
    sum_value: float = 0.0
    total_count: int = 0

    def __post_init__(self) -> None:
        if not self.counts:
            self.counts = [0] * len(self.buckets)

    def observe(self, value: float) -> None:
        self.total_count += 1
        self.sum_value += value
        idx = bisect_right(self.buckets, value)
        for i in range(idx, len(self.buckets)):
            self.counts[i] += 1


class MetricsRegistry:
    """Central metric repository tracking Counters, Gauges, and Histograms."""

    def __init__(self, config: ObservabilityConfig | None = None) -> None:
        self.config = config or get_observability_config()
        self._lock = Lock()
        self._counters: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(dict)
        self._gauges: dict[str, dict[tuple[tuple[str, str], ...], float]] = defaultdict(dict)
        self._histograms: dict[str, dict[tuple[tuple[str, str], ...], HistogramSeries]] = (
            defaultdict(dict)
        )
        self._metadata: dict[str, dict[str, Any]] = {}

    def _validate_labels(self, labels: dict[str, str] | None) -> None:
        """Enforce strict cardinality boundaries against dangerous label identifiers."""
        if not labels:
            return
        for key in labels:
            clean_key = str(key).strip().lower()
            if clean_key in FORBIDDEN_LABEL_KEYS:
                raise HighCardinalityViolationError(label_name=clean_key)

    def register_metric(self, name: str, metric_type: MetricType, description: str = "") -> None:
        """Register metric metadata and documentation."""
        with self._lock:
            self._metadata[name] = {
                "name": name,
                "type": str(metric_type),
                "description": description,
            }

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: dict[str, str] | None = None,
        description: str = "",
    ) -> None:
        """Increment a monotonic counter series."""
        self._validate_labels(labels)
        key = format_label_tuple(labels)
        with self._lock:
            if name not in self._metadata:
                self._metadata[name] = {
                    "name": name,
                    "type": str(MetricType.COUNTER),
                    "description": description,
                }
            current = self._counters[name].get(key, 0.0)
            self._counters[name][key] = current + value

    def gauge(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        description: str = "",
    ) -> None:
        """Set a point-in-time gauge value."""
        self._validate_labels(labels)
        key = format_label_tuple(labels)
        with self._lock:
            if name not in self._metadata:
                self._metadata[name] = {
                    "name": name,
                    "type": str(MetricType.GAUGE),
                    "description": description,
                }
            self._gauges[name][key] = value

    def observe(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        description: str = "",
        custom_buckets: list[float] | None = None,
    ) -> None:
        """Record an observation into a bucketed histogram."""
        self._validate_labels(labels)
        key = format_label_tuple(labels)
        buckets = custom_buckets or self.config.latency_buckets
        with self._lock:
            if name not in self._metadata:
                self._metadata[name] = {
                    "name": name,
                    "type": str(MetricType.HISTOGRAM),
                    "description": description,
                }
            if key not in self._histograms[name]:
                self._histograms[name][key] = HistogramSeries(buckets=buckets)
            self._histograms[name][key].observe(value)

    def get_counter_value(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Retrieve scalar counter value for given label combination."""
        key = format_label_tuple(labels)
        with self._lock:
            return self._counters.get(name, {}).get(key, 0.0)

    def get_gauge_value(self, name: str, labels: dict[str, str] | None = None) -> float | None:
        """Retrieve gauge value for given label combination."""
        key = format_label_tuple(labels)
        with self._lock:
            return self._gauges.get(name, {}).get(key, None)

    def get_all_metrics(self) -> dict[str, Any]:
        """Export snapshot of all registered metric series and aggregated readings."""
        with self._lock:
            snapshot: dict[str, Any] = {
                "counters": {},
                "gauges": {},
                "histograms": {},
                "metadata": dict(self._metadata),
            }

            for name, series in self._counters.items():
                snapshot["counters"][name] = [
                    {"labels": dict(lbls), "value": val} for lbls, val in series.items()
                ]

            for name, series in self._gauges.items():
                snapshot["gauges"][name] = [
                    {"labels": dict(lbls), "value": val} for lbls, val in series.items()
                ]

            for name, hist_series in self._histograms.items():
                snapshot["histograms"][name] = [
                    {
                        "labels": dict(lbls),
                        "buckets": list(zip(hist.buckets, hist.counts, strict=False)),
                        "count": hist.total_count,
                        "sum": hist.sum_value,
                    }
                    for lbls, hist in hist_series.items()
                ]

            return snapshot

    def get_snapshot(self) -> dict[str, Any]:
        """Alias for get_all_metrics."""
        return self.get_all_metrics()

    def reset(self) -> None:
        """Reset all metric series (used in automated testing)."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._metadata.clear()


# Global singleton metrics registry
_global_metrics_registry: MetricsRegistry | None = None


def get_metrics_registry() -> MetricsRegistry:
    """Singleton getter for the global metrics registry."""
    global _global_metrics_registry
    if _global_metrics_registry is None:
        _global_metrics_registry = MetricsRegistry()
    return _global_metrics_registry
