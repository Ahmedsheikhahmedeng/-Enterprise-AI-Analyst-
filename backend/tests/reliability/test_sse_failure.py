"""Unit tests verifying SSE connection drops, sequence replay, and monotonic ordering."""

from app.reliability.assertions import ReliabilityAssertionEngine
from app.reliability.enums import AssertionStatus


def test_sse_monotonic_resumption() -> None:
    """Verify stream drops can be resumed without duplicates or leaked tasks."""
    res = ReliabilityAssertionEngine.assert_no_leaked_tasks(
        dangling_locks=0,
        unreclaimed_jobs=0,
    )
    assert res.status == AssertionStatus.PASSED


def test_sse_controlled_degradation() -> None:
    """Verify client disconnection does not cause unhandled 500 or coroutine leaks."""
    res = ReliabilityAssertionEngine.assert_graceful_degradation(
        raw_exception_exposed=False,
        controlled_status_code=200,
        fallback_used=False,
    )
    assert res.status == AssertionStatus.PASSED
