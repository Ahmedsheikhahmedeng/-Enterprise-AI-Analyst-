"""Retry policies, exponential backoff with jitter, and error classification."""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import DBAPIError, OperationalError

from app.jobs.config import job_config
from app.jobs.exceptions import (
    JobCancellationError,
    JobIdempotencyConflictError,
    JobNotFoundError,
    JobPayloadTooLargeError,
    NonRetryableJobError,
    RetryableJobError,
)
from app.security.exceptions import (
    IDORViolationError,
    PromptInjectionDetectedError,
    SecurityPolicyViolationError,
    TenantIsolationViolationError,
)


class RetryPolicy:
    """Calculates exponential backoff delays with jitter for retrying failed jobs."""

    def __init__(
        self,
        max_attempts: int = job_config.DEFAULT_MAX_ATTEMPTS,
        initial_delay: float = job_config.RETRY_INITIAL_DELAY_SECONDS,
        max_delay: float = job_config.RETRY_MAX_DELAY_SECONDS,
        backoff_factor: float = job_config.RETRY_BACKOFF_FACTOR,
        jitter: bool = job_config.RETRY_JITTER,
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def compute_delay(self, attempt: int) -> float:
        """Compute exponential backoff delay in seconds for the given attempt index (1-based).

        Formula: min(max_delay, initial_delay * (backoff_factor ** (attempt - 1)))
        If jitter is enabled: uniform random between 0.5 * delay and 1.5 * delay.
        """
        exponent = max(0, attempt - 1)
        raw_delay = self.initial_delay * (self.backoff_factor**exponent)
        capped_delay = min(self.max_delay, raw_delay)

        if self.jitter:
            low = capped_delay * 0.5
            high = capped_delay * 1.5
            return round(random.uniform(low, high), 3)
        return round(capped_delay, 3)

    def compute_next_retry_at(self, attempt: int) -> datetime:
        """Calculate the UTC timestamp for the next retry attempt."""
        delay = self.compute_delay(attempt)
        return datetime.now(UTC) + timedelta(seconds=delay)


class RetryClassifier:
    """Classifies exceptions as transient/retryable or permanent/non-retryable."""

    # Explicit non-retryable exception types
    NON_RETRYABLE_TYPES: tuple[type[Exception], ...] = (
        NonRetryableJobError,
        JobCancellationError,
        JobIdempotencyConflictError,
        JobNotFoundError,
        JobPayloadTooLargeError,
        SecurityPolicyViolationError,
        TenantIsolationViolationError,
        IDORViolationError,
        PromptInjectionDetectedError,
        ValueError,
        TypeError,
        KeyError,
        PermissionError,
    )

    # Explicit retryable exception types
    RETRYABLE_TYPES: tuple[type[Exception], ...] = (
        RetryableJobError,
        OperationalError,
        DBAPIError,
        ConnectionError,
        TimeoutError,
    )

    @classmethod
    def is_retryable(cls, exc: Exception) -> bool:
        """Determine if an exception should trigger a retry attempt."""
        # 1. Check if the exception explicitly declares retryability
        if hasattr(exc, "retryable"):
            return bool(exc.retryable)

        # 2. Check for explicit non-retryable classes
        if isinstance(exc, cls.NON_RETRYABLE_TYPES):
            return False

        # 3. Check for explicit retryable classes
        if isinstance(exc, cls.RETRYABLE_TYPES):
            return True

        # 4. Check for common transient network / HTTP status codes if available
        exc_str = str(exc).lower()
        return any(
            keyword in exc_str
            for keyword in (
                "timeout",
                "connection refused",
                "temporarily unavailable",
                "rate limit",
                "429",
                "503",
            )
        )
