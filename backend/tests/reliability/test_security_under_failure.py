"""Unit tests verifying security enforcement and lack of fail-open bypass during degradation."""

from app.reliability.assertions import ReliabilityAssertionEngine
from app.reliability.enums import AssertionStatus


def test_no_fail_open_security_bypass() -> None:
    """Verify that system degradation never allows unauthenticated or unauthorized access."""
    res = ReliabilityAssertionEngine.assert_security_preserved(
        unauthenticated_requests_allowed=0,
        rbac_bypassed=False,
    )
    assert res.status == AssertionStatus.PASSED
    assert res.is_passed is True


def test_security_bypass_detected() -> None:
    """Verify detection if an unauthenticated request slipped through."""
    res = ReliabilityAssertionEngine.assert_security_preserved(
        unauthenticated_requests_allowed=1,
        rbac_bypassed=True,
    )
    assert res.status == AssertionStatus.FAILED
    assert res.is_passed is False
