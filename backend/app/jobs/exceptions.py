"""Domain exceptions for background jobs and distributed worker system."""

from typing import Any


class JobError(Exception):
    """Base exception for all job errors."""

    def __init__(self, message: str, code: str = "JOB_ERROR", retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


class JobNotFoundError(JobError):
    """Raised when a job is not found or inaccessible."""

    def __init__(self, job_id: Any):
        super().__init__(f"Job {job_id} not found", code="JOB_NOT_FOUND", retryable=False)
        self.job_id = str(job_id)


class InvalidJobStateTransitionError(JobError):
    """Raised when attempting an invalid status transition."""

    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            f"Cannot transition job from '{current_status}' to '{target_status}'",
            code="INVALID_JOB_STATE_TRANSITION",
            retryable=False,
        )
        self.current_status = current_status
        self.target_status = target_status


class JobIdempotencyConflictError(JobError):
    """Raised when a job with identical idempotency key has different payload hash."""

    def __init__(self, idempotency_key: str):
        super().__init__(
            f"Idempotency key '{idempotency_key}' already used with different payload",
            code="JOB_IDEMPOTENCY_CONFLICT",
            retryable=False,
        )
        self.idempotency_key = idempotency_key


class JobCancellationError(JobError):
    """Raised when a job execution is aborted due to cancellation."""

    def __init__(self, job_id: Any, reason: str = "Job cancelled by user"):
        super().__init__(f"Job {job_id} cancelled: {reason}", code="JOB_CANCELLED", retryable=False)
        self.job_id = str(job_id)
        self.reason = reason


class JobPayloadTooLargeError(JobError):
    """Raised when a job payload exceeds maximum allowed size."""

    def __init__(self, size_bytes: int, max_bytes: int):
        super().__init__(
            f"Job payload size {size_bytes} bytes exceeds limit of {max_bytes} bytes",
            code="JOB_PAYLOAD_TOO_LARGE",
            retryable=False,
        )


class JobQueueFullError(JobError):
    """Raised when queue depth exceeds backpressure limits."""

    def __init__(self, current_depth: int, max_depth: int):
        super().__init__(
            f"Job queue saturated (depth {current_depth} >= {max_depth})",
            code="JOB_QUEUE_FULL",
            retryable=True,
        )


class JobWorkerTimeoutError(JobError):
    """Raised when a job exceeds its maximum allowable execution time."""

    def __init__(self, job_id: Any, duration_seconds: float):
        super().__init__(
            f"Job {job_id} exceeded execution timeout ({duration_seconds:.1f}s)",
            code="JOB_WORKER_TIMEOUT",
            retryable=True,
        )


class RetryableJobError(JobError):
    """Explicitly retryable error encountered during task execution."""

    def __init__(self, message: str, code: str = "RETRYABLE_JOB_ERROR"):
        super().__init__(message, code=code, retryable=True)


class NonRetryableJobError(JobError):
    """Explicitly non-retryable fatal error encountered during task execution."""

    def __init__(self, message: str, code: str = "NON_RETRYABLE_JOB_ERROR"):
        super().__init__(message, code=code, retryable=False)
