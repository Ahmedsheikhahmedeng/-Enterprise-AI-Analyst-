"""Deep telemetry and instrumentation for Enterprise Data Connectors."""

from functools import lru_cache

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class ConnectorInstrumentation:
    """Low-cardinality metrics recorder for Data Connectors and Data Sources."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_connection_test(self, connector_type: str, success: bool, latency_ms: float) -> None:
        status = "success" if success else "failure"
        labels = {"connector_type": connector_type.lower(), "status": status}
        self.metrics.increment(
            "connector_connection_total",
            value=1.0,
            labels=labels,
            description="Total connector connection test attempts",
        )
        self.metrics.observe(
            "connector_connection_duration_ms",
            value=latency_ms,
            labels=labels,
            description="Latency of connector connection tests in milliseconds",
        )

    def record_schema_discovery(
        self, connector_type: str, success: bool, duration_ms: float
    ) -> None:
        status = "success" if success else "failure"
        labels = {"connector_type": connector_type.lower(), "status": status}
        self.metrics.increment(
            "connector_schema_discovery_total",
            value=1.0,
            labels=labels,
            description="Total connector schema discovery runs",
        )
        self.metrics.observe(
            "connector_schema_discovery_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Latency of connector schema discovery operations in milliseconds",
        )

    def record_query_execution(
        self, connector_type: str, success: bool, duration_ms: float, row_count: int = 0
    ) -> None:
        status = "success" if success else "failure"
        labels = {"connector_type": connector_type.lower(), "status": status}
        self.metrics.increment(
            "connector_query_total",
            value=1.0,
            labels=labels,
            description="Total connector queries executed",
        )
        self.metrics.observe(
            "connector_query_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Latency of connector query executions in milliseconds",
        )
        if success:
            self.metrics.increment(
                "connector_query_rows_total",
                value=float(row_count),
                labels={"connector_type": connector_type.lower()},
                description="Total rows returned by connector queries",
            )

    def record_sync_run(
        self, connector_type: str, sync_type: str, status: str, duration_ms: float
    ) -> None:
        labels = {
            "connector_type": connector_type.lower(),
            "sync_type": sync_type.lower(),
            "status": status.lower(),
        }
        self.metrics.increment(
            "connector_sync_runs_total",
            value=1.0,
            labels=labels,
            description="Total connector data synchronization runs",
        )
        self.metrics.observe(
            "connector_sync_duration_ms",
            value=duration_ms,
            labels=labels,
            description="Duration of connector synchronization operations in milliseconds",
        )


@lru_cache(maxsize=1)
def get_connector_instrumentation() -> ConnectorInstrumentation:
    """Singleton getter for connector telemetry instrumentation."""
    return ConnectorInstrumentation()
