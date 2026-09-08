"""Deep instrumentation for SQL Agent stages and execution metrics."""

from app.observability.metrics import MetricsRegistry, get_metrics_registry


class SQLInstrumentation:
    """Instruments SQL schema discovery, planning, validation, execution, and analysis."""

    def __init__(self, metrics: MetricsRegistry | None = None) -> None:
        self.metrics = metrics or get_metrics_registry()

    def record_query_execution(
        self,
        duration_ms: float,
        rows_returned: int = 0,
        status: str = "ok",
        error_type: str | None = None,
        is_timeout: bool = False,
    ) -> None:
        """Record SQL execution outcomes, row counts, and latency."""
        clean_status = status.lower()
        labels = {"status": clean_status}

        self.metrics.increment(
            "sql_queries_total",
            value=1.0,
            labels=labels,
            description="Total SQL queries executed",
        )
        self.metrics.increment(
            "enterprise_ai_sql_queries_total",
            value=1.0,
            labels=labels,
            description="Enterprise AI total SQL queries executed",
        )

        self.metrics.observe(
            "sql_query_duration_ms",
            value=duration_ms,
            labels=labels,
            description="SQL query execution latency in milliseconds",
        )

        if rows_returned > 0:
            self.metrics.increment(
                "sql_rows_returned",
                value=float(rows_returned),
                labels=labels,
                description="Total rows returned by SQL queries",
            )

        if clean_status != "ok" or error_type:
            err_labels = {"error_type": error_type or "unknown"}
            self.metrics.increment(
                "sql_query_failures_total",
                value=1.0,
                labels=err_labels,
                description="Total SQL query execution failures",
            )
            self.metrics.increment(
                "enterprise_ai_sql_query_failures_total",
                value=1.0,
                labels=err_labels,
                description="Enterprise AI total SQL query execution failures",
            )

        if is_timeout:
            self.metrics.increment(
                "sql_timeout_total",
                value=1.0,
                labels={},
                description="Total SQL queries timing out",
            )

    def record_validation_failure(self, rule_name: str = "unknown") -> None:
        """Record SQL AST or security validation failures."""
        self.metrics.increment(
            "sql_validation_failures_total",
            value=1.0,
            labels={"rule": rule_name.lower()},
            description="Total SQL queries rejected by validation safety rules",
        )

    def record_stage_latency(self, stage: str, duration_ms: float, status: str = "ok") -> None:
        """Record latency across SQL pipeline stages (schema_discovery, planning, validation, execution, analysis, provenance)."""
        clean_stage = stage.lower().strip()
        self.metrics.observe(
            f"sql_stage_{clean_stage}_duration_ms",
            value=duration_ms,
            labels={"stage": clean_stage, "status": status.lower()},
            description=f"SQL stage {clean_stage} latency in milliseconds",
        )


# Global singleton
_global_sql_instrumentation: SQLInstrumentation | None = None


def get_sql_instrumentation() -> SQLInstrumentation:
    """Singleton getter for SQLInstrumentation."""
    global _global_sql_instrumentation
    if _global_sql_instrumentation is None:
        _global_sql_instrumentation = SQLInstrumentation()
    return _global_sql_instrumentation
