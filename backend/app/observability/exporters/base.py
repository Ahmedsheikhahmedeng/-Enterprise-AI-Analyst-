"""Abstract interface for metrics and telemetry exporters."""

from abc import ABC, abstractmethod
from typing import Any

from app.observability.metrics import MetricsRegistry


class MetricsExporter(ABC):
    """Base interface for transforming and exporting registry metrics to monitoring sinks."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self.registry = registry

    def export(self, registry: MetricsRegistry | None = None) -> Any:
        """Export metrics using bound or provided registry."""
        target = registry or self.registry
        if target is None:
            from app.observability.metrics import get_metrics_registry

            target = get_metrics_registry()
        return self.export_metrics(target)

    @abstractmethod
    def export_metrics(self, registry: MetricsRegistry) -> Any:
        """Export or format metrics from the given registry."""
        pass
