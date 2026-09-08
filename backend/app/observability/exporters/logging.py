"""Structured JSON logging metrics exporter."""

from typing import Any

from app.core.logging import get_logger
from app.observability.exporters.base import MetricsExporter
from app.observability.metrics import MetricsRegistry

logger = get_logger("observability.exporter.logging")


class LoggingExporter(MetricsExporter):
    """Outputs serialized metric snapshots into structured JSON log streams."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        super().__init__(registry)

    def export_metrics(self, registry: MetricsRegistry) -> dict[str, Any]:
        """Collect and log metric readings via structured logger."""
        snapshot = registry.get_all_metrics()
        logger.info(
            "Exporting telemetry metrics snapshot",
            metrics_count=len(snapshot["counters"])
            + len(snapshot["gauges"])
            + len(snapshot["histograms"]),
        )
        return snapshot
