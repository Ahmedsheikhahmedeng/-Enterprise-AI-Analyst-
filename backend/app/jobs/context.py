"""Job execution context passed to task handlers."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobContext:
    """Immutable runtime execution context for a task handler."""

    job_id: uuid.UUID
    organization_id: uuid.UUID
    job_type: str
    attempt: int
    max_attempts: int
    created_by: uuid.UUID | None = None
    trace_id: str | None = None
    request_id: str | None = None
    worker_id: str | None = None
    _cancellation_checker: Callable[[], bool] | None = None
    _progress_reporter: Callable[[float, str | None], None] | None = None

    def is_cancelled(self) -> bool:
        """Check whether the job has been cancelled at this checkpoint."""
        if self._cancellation_checker:
            return self._cancellation_checker()
        return False

    def report_progress(self, progress: float, message: str | None = None) -> None:
        """Report normalized task progress (0.0 to 1.0) and optional status message."""
        if self._progress_reporter:
            clamped = max(0.0, min(1.0, float(progress)))
            self._progress_reporter(clamped, message)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for logging and tracing."""
        return {
            "job_id": str(self.job_id),
            "organization_id": str(self.organization_id),
            "job_type": self.job_type,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "created_by": str(self.created_by) if self.created_by else None,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "worker_id": self.worker_id,
        }
