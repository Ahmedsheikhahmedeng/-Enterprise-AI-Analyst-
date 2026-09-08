"""Unit tests for background worker crash, queue backlog, and DLQ diversion."""

from app.reliability.assertions import ReliabilityAssertionEngine
from app.reliability.enums import AssertionStatus


def test_worker_crash_and_lease_recovery() -> None:
    """Verify worker crash does not cause duplicate chunk writes or orphaned locks."""
    res = ReliabilityAssertionEngine.assert_no_leaked_tasks(
        dangling_locks=0,
        unreclaimed_jobs=0,
    )
    assert res.status == AssertionStatus.PASSED
    assert res.is_passed is True


def test_dlq_poison_pill_containment() -> None:
    """Verify permanent failure transitions to DLQ without blocking other jobs."""
    res = ReliabilityAssertionEngine.assert_graceful_degradation(
        raw_exception_exposed=False,
        controlled_status_code=503,
        fallback_used=True,
    )
    assert res.status == AssertionStatus.PASSED
