"""Observability and Prometheus metrics instrumentation for Background Jobs."""

from app.observability.metrics import get_metrics_registry


class JobMetrics:
    """Convenience wrapper recording low-cardinality telemetry for jobs and workers."""

    @classmethod
    def record_job_dispatched(cls, job_type: str, priority: str) -> None:
        """Increment dispatched job counter."""
        reg = get_metrics_registry()
        reg.increment(
            "jobs_total",
            labels={"job_type": job_type, "priority": priority},
            description="Total number of jobs submitted/dispatched",
        )
        reg.increment(
            "queue_enqueue_total",
            labels={"priority": priority},
            description="Total jobs pushed to broker queue",
        )

    @classmethod
    def record_job_started(cls, job_type: str) -> None:
        """Track running jobs gauge."""
        reg = get_metrics_registry()
        reg.increment(
            "queue_dequeue_total",
            description="Total jobs popped/dequeued from queue",
        )

    @classmethod
    def record_job_completed(cls, job_type: str, duration_ms: float, attempt: int) -> None:
        """Record successful completion, latency and attempt count."""
        reg = get_metrics_registry()
        reg.increment(
            "jobs_completed_total",
            labels={"job_type": job_type},
            description="Total number of successfully completed jobs",
        )
        reg.observe(
            "job_duration_ms",
            value=duration_ms,
            labels={"job_type": job_type, "status": "completed"},
            description="Job execution duration in milliseconds",
        )
        reg.observe(
            "job_attempts",
            value=float(attempt),
            labels={"job_type": job_type},
            description="Attempts required until terminal completion or failure",
        )
        reg.increment("worker_jobs_processed_total")

    @classmethod
    def record_job_retry_scheduled(cls, job_type: str) -> None:
        """Increment retried jobs counter."""
        reg = get_metrics_registry()
        reg.increment(
            "jobs_retried_total",
            labels={"job_type": job_type},
            description="Total jobs scheduled for retry after transient failure",
        )

    @classmethod
    def record_job_failed(cls, job_type: str, duration_ms: float) -> None:
        """Increment failed jobs counter."""
        reg = get_metrics_registry()
        reg.increment(
            "jobs_failed_total",
            labels={"job_type": job_type},
            description="Total jobs experiencing execution failure",
        )
        reg.observe(
            "job_duration_ms",
            value=duration_ms,
            labels={"job_type": job_type, "status": "failed"},
            description="Job execution duration in milliseconds",
        )
        reg.increment("worker_job_failures_total")

    @classmethod
    def record_job_dead_lettered(cls, job_type: str) -> None:
        """Increment dead lettered jobs counter."""
        reg = get_metrics_registry()
        reg.increment(
            "jobs_dead_lettered_total",
            labels={"job_type": job_type},
            description="Total jobs routed to dead letter state",
        )

    @classmethod
    def record_job_cancelled(cls, job_type: str) -> None:
        """Increment cancelled jobs counter."""
        reg = get_metrics_registry()
        reg.increment(
            "jobs_cancelled_total",
            labels={"job_type": job_type},
            description="Total jobs cancelled prior to or during execution",
        )
