"""Prometheus exposition text format metrics exporter."""

from app.observability.exporters.base import MetricsExporter
from app.observability.metrics import MetricsRegistry


class PrometheusExporter(MetricsExporter):
    """Formats in-memory MetricsRegistry data into standard Prometheus text exposition format."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        super().__init__(registry)

    def format_labels(self, labels: dict[str, str], extra: dict[str, str] | None = None) -> str:
        """Format key-value pairs into standard label string {k="v",...}."""
        all_labels = dict(labels)
        if extra:
            all_labels.update(extra)
        if not all_labels:
            return ""
        items = [f'{k}="{v}"' for k, v in sorted(all_labels.items())]
        return "{" + ",".join(items) + "}"

    def export_metrics(self, registry: MetricsRegistry) -> str:
        """Generate Prometheus exposition text format (version 0.0.4)."""
        metrics_data = registry.get_all_metrics()
        counters = metrics_data["counters"]
        gauges = metrics_data["gauges"]
        histograms = metrics_data["histograms"]
        metadata = metrics_data["metadata"]

        lines: list[str] = []

        # 1. Counters
        for name, series_list in counters.items():
            meta = metadata.get(name, {})
            desc = meta.get("description") or f"Counter metric {name}"
            lines.append(f"# HELP {name} {desc}")
            lines.append(f"# TYPE {name} counter")
            for entry in series_list:
                lbls_str = self.format_labels(entry["labels"])
                lines.append(f"{name}{lbls_str} {entry['value']}")

        # 2. Gauges
        for name, series_list in gauges.items():
            meta = metadata.get(name, {})
            desc = meta.get("description") or f"Gauge metric {name}"
            lines.append(f"# HELP {name} {desc}")
            lines.append(f"# TYPE {name} gauge")
            for entry in series_list:
                lbls_str = self.format_labels(entry["labels"])
                lines.append(f"{name}{lbls_str} {entry['value']}")

        # 3. Histograms
        for name, series_list in histograms.items():
            meta = metadata.get(name, {})
            desc = meta.get("description") or f"Histogram metric {name}"
            lines.append(f"# HELP {name} {desc}")
            lines.append(f"# TYPE {name} histogram")
            for entry in series_list:
                base_lbls = entry["labels"]
                buckets = entry["buckets"]
                count = entry["count"]
                sum_val = entry["sum"]

                for upper_bound, b_count in buckets:
                    lbls_str = self.format_labels(base_lbls, extra={"le": str(upper_bound)})
                    lines.append(f"{name}_bucket{lbls_str} {b_count}")

                inf_lbls_str = self.format_labels(base_lbls, extra={"le": "+Inf"})
                lines.append(f"{name}_bucket{inf_lbls_str} {count}")

                cnt_lbls_str = self.format_labels(base_lbls)
                lines.append(f"{name}_count{cnt_lbls_str} {count}")
                lines.append(f"{name}_sum{cnt_lbls_str} {sum_val}")

        return "\n".join(lines) + "\n"
