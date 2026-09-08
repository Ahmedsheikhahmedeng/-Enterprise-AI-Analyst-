"""Deep telemetry and instrumentation for Dataset Ingestion and Materialization."""

from functools import lru_cache

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class DatasetInstrumentation:
    """Low-cardinality metrics recorder for dataset materialization pipelines."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_ingestion_started(self, source_type: str) -> None:
        labels = {"source_type": source_type.lower()}
        self.metrics.increment(
            "dataset_ingestion_started_total",
            value=1.0,
            labels=labels,
            description="Total number of dataset ingestion runs initiated",
        )

    def record_ingestion_completed(
        self,
        source_type: str,
        rows: int,
        duration_s: float,
        quality_score: float,
        bytes_count: int = 0,
    ) -> None:
        labels = {"source_type": source_type.lower(), "status": "completed"}
        self.metrics.increment(
            "dataset_ingestion_completed_total",
            value=1.0,
            labels=labels,
            description="Total number of dataset ingestion runs completed successfully",
        )
        self.metrics.increment(
            "dataset_rows_processed_total",
            value=float(rows),
            labels=labels,
            description="Total number of tabular rows processed across datasets",
        )
        self.metrics.observe(
            "dataset_ingestion_duration_seconds",
            value=duration_s,
            labels=labels,
            description="Duration of dataset ingestion in seconds",
        )
        self.metrics.observe(
            "dataset_quality_score",
            value=quality_score,
            labels=labels,
            description="Evaluated dataset quality score",
        )
        if bytes_count > 0:
            self.metrics.increment(
                "dataset_bytes_processed_total",
                value=float(bytes_count),
                labels=labels,
                description="Total bytes processed during dataset materialization",
            )

    def record_ingestion_failed(self, source_type: str) -> None:
        labels = {"source_type": source_type.lower(), "status": "failed"}
        self.metrics.increment(
            "dataset_ingestion_failed_total",
            value=1.0,
            labels=labels,
            description="Total number of dataset ingestion runs that failed",
        )


@lru_cache(maxsize=1)
def get_dataset_instrumentation() -> DatasetInstrumentation:
    """Singleton getter for DatasetInstrumentation."""
    return DatasetInstrumentation()
