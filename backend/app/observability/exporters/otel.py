"""OpenTelemetry standard schema transformation and export abstraction."""

import time
from typing import Any

from app.observability.exporters.base import MetricsExporter
from app.observability.metrics import MetricsRegistry
from app.observability.models import SpanRecord


class OpenTelemetryExporter(MetricsExporter):
    """Transforms internal telemetry metrics and spans into standard OTel-compliant schema dictionaries."""

    def __init__(
        self,
        registry: MetricsRegistry | None = None,
        service_name: str = "enterprise-ai-analyst",
        service_version: str = "1.0.0",
    ) -> None:
        super().__init__(registry)
        self.service_name = service_name
        self.service_version = service_version

    def export_metrics(self, registry: MetricsRegistry) -> dict[str, Any]:
        """Convert in-memory metrics into OTel ResourceMetrics data structure."""
        data = registry.get_all_metrics()
        now_ns = int(time.time() * 1_000_000_000)

        otel_metrics: list[dict[str, Any]] = []

        # Convert counters
        for name, series in data["counters"].items():
            for item in series:
                otel_metrics.append(
                    {
                        "name": name,
                        "description": data["metadata"].get(name, {}).get("description", ""),
                        "unit": "1",
                        "data": {
                            "dataPoints": [
                                {
                                    "attributes": [
                                        {"key": k, "value": {"stringValue": v}}
                                        for k, v in item["labels"].items()
                                    ],
                                    "startTimeUnixNano": now_ns,
                                    "timeUnixNano": now_ns,
                                    "asDouble": item["value"],
                                }
                            ]
                        },
                    }
                )

        return {
            "resourceMetrics": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self.service_name}},
                            {
                                "key": "service.version",
                                "value": {"stringValue": self.service_version},
                            },
                        ]
                    },
                    "scopeMetrics": [
                        {
                            "scope": {"name": "app.observability", "version": "1.0.0"},
                            "metrics": otel_metrics,
                        }
                    ],
                }
            ]
        }

    def export_spans(self, spans: list[SpanRecord]) -> dict[str, Any]:
        """Convert SpanRecord objects into standard OTel ResourceSpans structure."""
        otel_spans: list[dict[str, Any]] = []
        for s in spans:
            otel_spans.append(
                {
                    "traceId": s.trace_id,
                    "spanId": s.span_id,
                    "parentSpanId": s.parent_span_id or "",
                    "name": s.name,
                    "kind": f"SPAN_KIND_{s.kind.upper()}",
                    "startTimeUnixNano": int(s.start_time * 1_000_000_000),
                    "endTimeUnixNano": int((s.end_time or s.start_time) * 1_000_000_000),
                    "status": {
                        "code": f"STATUS_CODE_{s.status.upper()}",
                        "message": s.error_message or "",
                    },
                    "attributes": [
                        {"key": k, "value": {"stringValue": str(v)}}
                        for k, v in s.attributes.items()
                    ],
                }
            )

        return {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": self.service_name}},
                            {
                                "key": "service.version",
                                "value": {"stringValue": self.service_version},
                            },
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": "app.observability.tracer", "version": "1.0.0"},
                            "spans": otel_spans,
                        }
                    ],
                }
            ]
        }
