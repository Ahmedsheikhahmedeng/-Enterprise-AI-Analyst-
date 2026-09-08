"""Unit tests for background jobs and distributed worker subsystem."""

import uuid
from typing import Any

import pytest

from app.jobs.cancellation import JobCancellationManager
from app.jobs.context import JobContext
from app.jobs.exceptions import (
    InvalidJobStateTransitionError,
    JobCancellationError,
    JobError,
    JobIdempotencyConflictError,
    NonRetryableJobError,
    RetryableJobError,
)
from app.jobs.idempotency import JobIdempotencyManager
from app.jobs.lifecycle import JobLifecycleManager
from app.jobs.policies import JobSecurityPolicy
from app.jobs.queue import InMemoryJobQueue
from app.jobs.registry import TaskRegistry
from app.jobs.retry import RetryClassifier, RetryPolicy
from app.jobs.schemas import JobStatus
from app.security.exceptions import SecurityPolicyViolationError, TenantIsolationViolationError


class DummyTask:
    """Mock task handler for registry testing."""

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        return {"result": "ok"}


def test_job_state_machine_valid_transitions() -> None:
    """Ensure legal state machine transitions are accepted."""
    JobLifecycleManager.validate_transition(JobStatus.QUEUED.value, JobStatus.RUNNING.value)
    JobLifecycleManager.validate_transition(JobStatus.RUNNING.value, JobStatus.COMPLETED.value)
    JobLifecycleManager.validate_transition(JobStatus.RUNNING.value, JobStatus.FAILED.value)
    JobLifecycleManager.validate_transition(
        JobStatus.RUNNING.value, JobStatus.RETRY_SCHEDULED.value
    )
    JobLifecycleManager.validate_transition(JobStatus.RUNNING.value, JobStatus.CANCELLED.value)
    JobLifecycleManager.validate_transition(JobStatus.QUEUED.value, JobStatus.CANCELLED.value)
    JobLifecycleManager.validate_transition(JobStatus.RETRY_SCHEDULED.value, JobStatus.QUEUED.value)
    JobLifecycleManager.validate_transition(JobStatus.FAILED.value, JobStatus.DEAD_LETTER.value)
    JobLifecycleManager.validate_transition(JobStatus.FAILED.value, JobStatus.QUEUED.value)
    JobLifecycleManager.validate_transition(JobStatus.DEAD_LETTER.value, JobStatus.QUEUED.value)


def test_job_state_machine_invalid_transitions() -> None:
    """Ensure illegal transitions raise InvalidJobStateTransitionError."""
    with pytest.raises(InvalidJobStateTransitionError):
        JobLifecycleManager.validate_transition(JobStatus.COMPLETED.value, JobStatus.RUNNING.value)

    with pytest.raises(InvalidJobStateTransitionError):
        JobLifecycleManager.validate_transition(JobStatus.COMPLETED.value, JobStatus.QUEUED.value)

    with pytest.raises(InvalidJobStateTransitionError):
        JobLifecycleManager.validate_transition(JobStatus.CANCELLED.value, JobStatus.RUNNING.value)

    with pytest.raises(InvalidJobStateTransitionError):
        JobLifecycleManager.validate_transition(
            JobStatus.DEAD_LETTER.value, JobStatus.RUNNING.value
        )


def test_canonical_payload_hashing_determinism() -> None:
    """Payload hashing must be independent of dict iteration order and whitespace."""
    payload_a = {"alpha": 1, "beta": "test", "nested": {"b": 2, "a": 1}}
    payload_b = {"nested": {"a": 1, "b": 2}, "beta": "test", "alpha": 1}

    hash_a = JobIdempotencyManager.compute_payload_hash(payload_a)
    hash_b = JobIdempotencyManager.compute_payload_hash(payload_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64

    # Different payload must yield different hash
    payload_c = {"alpha": 2, "beta": "test", "nested": {"b": 2, "a": 1}}
    assert JobIdempotencyManager.compute_payload_hash(payload_c) != hash_a


def test_retry_policy_exponential_backoff_and_jitter() -> None:
    """Verify exponential backoff calculation and bounded jitter."""
    policy = RetryPolicy(
        max_attempts=4,
        initial_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        jitter=False,
    )

    assert policy.compute_delay(1) == 1.0
    assert policy.compute_delay(2) == 2.0
    assert policy.compute_delay(3) == 4.0
    assert policy.compute_delay(4) == 8.0
    assert policy.compute_delay(10) == 30.0  # Capped at max_delay

    # With jitter: delay must fall within [0.5 * delay, 1.5 * delay]
    jitter_policy = RetryPolicy(
        initial_delay=10.0,
        max_delay=60.0,
        backoff_factor=2.0,
        jitter=True,
    )
    for _ in range(20):
        delay = jitter_policy.compute_delay(1)
        assert 5.0 <= delay <= 15.0


def test_retry_classifier() -> None:
    """Classify retryable vs non-retryable exceptions accurately."""
    # Retryable
    assert RetryClassifier.is_retryable(RetryableJobError("Connection reset"))
    assert RetryClassifier.is_retryable(ConnectionError("Connection dropped"))
    assert RetryClassifier.is_retryable(TimeoutError("Socket timeout"))
    assert RetryClassifier.is_retryable(Exception("HTTP 429 Too Many Requests"))
    assert RetryClassifier.is_retryable(Exception("503 Service Unavailable"))

    # Non-retryable
    assert not RetryClassifier.is_retryable(NonRetryableJobError("Invalid config"))
    assert not RetryClassifier.is_retryable(JobCancellationError(uuid.uuid4()))
    assert not RetryClassifier.is_retryable(JobIdempotencyConflictError("key-1"))
    assert not RetryClassifier.is_retryable(TenantIsolationViolationError("Denied"))
    assert not RetryClassifier.is_retryable(SecurityPolicyViolationError("Secret detected"))
    assert not RetryClassifier.is_retryable(ValueError("Missing param"))
    assert not RetryClassifier.is_retryable(TypeError("Wrong type"))


def test_task_registry() -> None:
    """Ensure handlers can be registered, retrieved, and listed."""
    reg = TaskRegistry()
    reg.register("test_task", DummyTask)

    assert "test_task" in reg.list_types()
    handler = reg.get("test_task")
    assert isinstance(handler, DummyTask)

    with pytest.raises(JobError) as exc_info:
        reg.get("unknown_type")
    assert exc_info.value.code == "TASK_NOT_REGISTERED"


def test_job_security_payload_validation() -> None:
    """Validate payload size limits and prohibited secret detection."""
    # Valid payload
    JobSecurityPolicy.validate_payload({"doc_id": "123", "action": "parse"})

    # Prohibited secret keywords in keys
    with pytest.raises(SecurityPolicyViolationError):
        JobSecurityPolicy.validate_payload({"password": "secret_value"})

    with pytest.raises(SecurityPolicyViolationError):
        JobSecurityPolicy.validate_payload({"api_key": "some_token"})

    # Prohibited nested secret
    with pytest.raises(SecurityPolicyViolationError):
        JobSecurityPolicy.validate_payload({"config": {"access_token": "abc"}})


def test_cancellation_manager_checkpoints() -> None:
    """Ensure cancellation checkpoints register and trigger correctly."""
    job_id = uuid.uuid4()
    assert not JobCancellationManager.is_cancelled(job_id)

    JobCancellationManager.register_cancellation(job_id)
    assert JobCancellationManager.is_cancelled(job_id)

    with pytest.raises(JobCancellationError):
        JobCancellationManager.check_checkpoint(job_id)

    JobCancellationManager.unregister_cancellation(job_id)
    assert not JobCancellationManager.is_cancelled(job_id)


@pytest.mark.asyncio
async def test_in_memory_queue_priority_and_ack() -> None:
    """Verify in-memory queue FIFO priority ordering and ACK semantics."""
    queue = InMemoryJobQueue(visibility_timeout=60.0)

    id_low = uuid.uuid4()
    id_normal = uuid.uuid4()
    id_high = uuid.uuid4()

    # Enqueue low, normal, high in mixed order
    await queue.enqueue(id_low, "test", priority="low")
    await queue.enqueue(id_normal, "test", priority="normal")
    await queue.enqueue(id_high, "test", priority="high")

    depths = await queue.get_all_depths()
    assert depths["total_ready"] == 3
    assert depths["high"] == 1
    assert depths["normal"] == 1
    assert depths["low"] == 1

    # Dequeue must return high first, then normal, then low
    deq_1 = await queue.dequeue("worker-1", timeout=0.5)
    assert deq_1 == id_high

    deq_2 = await queue.dequeue("worker-1", timeout=0.5)
    assert deq_2 == id_normal

    deq_3 = await queue.dequeue("worker-1", timeout=0.5)
    assert deq_3 == id_low

    # In-flight count should now be 3
    depths_after = await queue.get_all_depths()
    assert depths_after["inflight"] == 3
    assert depths_after["total_ready"] == 0

    # ACK one job
    await queue.ack(id_high)
    depths_ack = await queue.get_all_depths()
    assert depths_ack["inflight"] == 2


@pytest.mark.asyncio
async def test_in_memory_queue_nack_and_requeue() -> None:
    """Verify NACK without delay pushes back to ready queue immediately."""
    queue = InMemoryJobQueue(visibility_timeout=60.0)
    job_id = uuid.uuid4()

    await queue.enqueue(job_id, "test", priority="normal")
    deq = await queue.dequeue("worker-1")
    assert deq == job_id

    # NACK immediately
    await queue.nack(job_id, delay_seconds=0.0)
    depths = await queue.get_all_depths()
    assert depths["total_ready"] == 1
    assert depths["inflight"] == 0

    # Should be dequeueable again
    deq_again = await queue.dequeue("worker-2")
    assert deq_again == job_id
    await queue.ack(job_id)


@pytest.mark.asyncio
async def test_in_memory_queue_visibility_timeout_reclamation() -> None:
    """Verify expired in-flight jobs are reclaimed when worker crashes without ACK."""
    # Short visibility timeout (0.1s)
    queue = InMemoryJobQueue(visibility_timeout=0.1)
    job_id = uuid.uuid4()

    await queue.enqueue(job_id, "test", priority="normal")
    deq = await queue.dequeue("worker-crash")
    assert deq == job_id

    # Wait for visibility timeout to expire
    import asyncio

    await asyncio.sleep(0.15)

    # Next dequeue must automatically reclaim the expired in-flight job
    deq_reclaimed = await queue.dequeue("worker-recovery")
    assert deq_reclaimed == job_id
    await queue.ack(job_id)
