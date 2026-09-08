"""Unit tests verifying multi-tenant data and operational isolation under failure."""

from app.reliability.assertions import ReliabilityAssertionEngine
from app.reliability.enums import AssertionStatus


def test_tenant_b_isolated_from_tenant_a_chaos() -> None:
    """Verify Tenant B maintains 100% success rate even when Tenant A undergoes 100% failure."""
    res = ReliabilityAssertionEngine.assert_tenant_isolation(
        cross_tenant_data_leaked=False,
        tenant_b_affected_by_a=False,
        tenant_b_success_rate=1.0,
    )
    assert res.status == AssertionStatus.PASSED
    assert res.is_passed is True


def test_tenant_isolation_breach_detected() -> None:
    """Verify that any cross-tenant data leak is detected and triggers assertion failure."""
    res = ReliabilityAssertionEngine.assert_tenant_isolation(
        cross_tenant_data_leaked=True,
        tenant_b_affected_by_a=True,
        tenant_b_success_rate=0.85,
    )
    assert res.status == AssertionStatus.FAILED
    assert res.is_passed is False
