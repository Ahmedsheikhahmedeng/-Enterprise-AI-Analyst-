"""Tests for FinOps Readiness Evaluator and hard blocking constraints."""

from app.finops.enums import FinOpsReadinessDecision
from app.finops.readiness import FinOpsReadinessEvaluator


def test_finops_readiness_fully_ready() -> None:
    """System with 100% pricing coverage, zero violations, and full attribution is READY."""
    result = FinOpsReadinessEvaluator.evaluate(
        pricing_coverage_percent=100.0,
        attribution_completeness_percent=100.0,
        reconciliation_matched_percent=100.0,
        open_critical_anomalies=0,
        budgets_exhausted=0,
        has_negative_cost_records=False,
        has_tenant_leakage=False,
    )
    assert result.decision == FinOpsReadinessDecision.READY
    assert result.score >= 90.0
    assert len(result.blockers) == 0


def test_finops_readiness_hard_blocker_tenant_leakage() -> None:
    """Tenant cost leakage is a hard blocker causing immediate NOT_READY state."""
    result = FinOpsReadinessEvaluator.evaluate(
        pricing_coverage_percent=100.0,
        attribution_completeness_percent=100.0,
        reconciliation_matched_percent=100.0,
        open_critical_anomalies=0,
        budgets_exhausted=0,
        has_tenant_leakage=True,  # Hard Blocker!
    )
    assert result.decision == FinOpsReadinessDecision.NOT_READY
    assert any("Tenant cost isolation failure" in blocker for blocker in result.blockers)


def test_finops_readiness_hard_blocker_negative_cost() -> None:
    """Negative cost detection in the ledger causes immediate NOT_READY state."""
    result = FinOpsReadinessEvaluator.evaluate(
        pricing_coverage_percent=100.0,
        attribution_completeness_percent=100.0,
        reconciliation_matched_percent=100.0,
        open_critical_anomalies=0,
        budgets_exhausted=0,
        has_negative_cost_records=True,  # Hard Blocker!
    )
    assert result.decision == FinOpsReadinessDecision.NOT_READY
    assert any("Negative cost" in blocker for blocker in result.blockers)


def test_finops_readiness_ready_with_warnings() -> None:
    """Minor attribution gaps or exhausted budgets produce READY_WITH_WARNINGS."""
    result = FinOpsReadinessEvaluator.evaluate(
        pricing_coverage_percent=96.0,
        attribution_completeness_percent=92.0,  # Warning < 95%
        reconciliation_matched_percent=95.0,
        open_critical_anomalies=0,
        budgets_exhausted=1,  # Warning
    )
    assert result.decision == FinOpsReadinessDecision.READY_WITH_WARNINGS
    assert len(result.warnings) > 0
    assert len(result.blockers) == 0
