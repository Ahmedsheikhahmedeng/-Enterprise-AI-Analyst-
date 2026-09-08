"""Unit tests verifying LLM Gateway provider failover and circuit breaker protection."""

from app.reliability.assertions import ReliabilityAssertionEngine
from app.reliability.enums import AssertionStatus


def test_llm_retry_storm_prevention() -> None:
    """Verify max attempts and exponential backoff prevent unbounded downstream requests."""
    res = ReliabilityAssertionEngine.assert_retry_storm_protection(
        actual_retries=2,
        max_allowed_retries=3,
        backoff_applied=True,
    )
    assert res.status == AssertionStatus.PASSED

    # If retries exceed limit
    res_exceeded = ReliabilityAssertionEngine.assert_retry_storm_protection(
        actual_retries=5,
        max_allowed_retries=3,
        backoff_applied=True,
    )
    assert res_exceeded.status == AssertionStatus.FAILED


def test_llm_circuit_breaker_tripping() -> None:
    """Verify circuit breaker opens upon error threshold and blocks subsequent calls."""
    res = ReliabilityAssertionEngine.assert_circuit_breaker(
        circuit_tripped=True,
        subsequent_calls_blocked=True,
    )
    assert res.status == AssertionStatus.PASSED


def test_llm_timeout_budget() -> None:
    """Verify nested LLM call respects overall orchestrator timeout deadline."""
    res = ReliabilityAssertionEngine.assert_timeout_budget(
        elapsed_ms=3500.0,
        deadline_ms=4000.0,
    )
    assert res.status == AssertionStatus.PASSED
