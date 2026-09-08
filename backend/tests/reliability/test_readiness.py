"""Unit tests for ProductionReadinessEvaluator and scoring engine."""

from app.reliability.enums import ReadinessDecision
from app.reliability.readiness import ProductionReadinessEvaluator
from app.reliability.scoring import ReliabilityScoringEngine


def test_production_readiness_all_green() -> None:
    """Verify READY verdict when all quality gates and assertions pass."""
    res = ProductionReadinessEvaluator.evaluate_readiness(
        backend_tests_passed=True,
        frontend_tests_passed=True,
        security_gates_passed=True,
        slo_breached=False,
        error_budget_remaining_pct=100.0,
        open_critical_incidents=0,
        data_integrity_failures=0,
        security_failures=0,
        isolation_failures=0,
        backup_verified=True,
        worker_fleet_healthy=True,
        llm_failover_verified=True,
    )
    assert res.decision == ReadinessDecision.READY
    assert len(res.blockers) == 0
    assert len(res.warnings) == 0
    assert res.composite_score == 100.0


def test_production_readiness_warnings_mode() -> None:
    """Verify READY_WITH_WARNINGS when error budget is low or backup unconfirmed."""
    res = ProductionReadinessEvaluator.evaluate_readiness(
        backend_tests_passed=True,
        frontend_tests_passed=True,
        security_gates_passed=True,
        slo_breached=False,
        error_budget_remaining_pct=15.0,  # low buffer triggers warning
        open_critical_incidents=0,
        data_integrity_failures=0,
        security_failures=0,
        isolation_failures=0,
        backup_verified=False,  # unconfirmed backup triggers warning
        worker_fleet_healthy=True,
        llm_failover_verified=True,
    )
    assert res.decision == ReadinessDecision.READY_WITH_WARNINGS
    assert len(res.blockers) == 0
    assert len(res.warnings) >= 1
    assert res.composite_score == 80.0


def test_production_readiness_hard_blockers() -> None:
    """Verify NOT_READY verdict immediately when critical failures are present."""
    # Data integrity failure
    res_integrity = ProductionReadinessEvaluator.evaluate_readiness(
        data_integrity_failures=1,
    )
    assert res_integrity.decision == ReadinessDecision.NOT_READY
    assert any("Data integrity" in b for b in res_integrity.blockers)

    # Security failure
    res_security = ProductionReadinessEvaluator.evaluate_readiness(
        security_failures=1,
    )
    assert res_security.decision == ReadinessDecision.NOT_READY
    assert any("Security validation" in b for b in res_security.blockers)

    # Isolation failure
    res_isolation = ProductionReadinessEvaluator.evaluate_readiness(
        isolation_failures=1,
    )
    assert res_isolation.decision == ReadinessDecision.NOT_READY
    assert any("Multi-tenant isolation" in b for b in res_isolation.blockers)

    # Open critical incident
    res_incident = ProductionReadinessEvaluator.evaluate_readiness(
        open_critical_incidents=2,
    )
    assert res_incident.decision == ReadinessDecision.NOT_READY
    assert any("SEV1/SEV2" in b for b in res_incident.blockers)


def test_reliability_scoring_calculation() -> None:
    """Verify deterministic scorecard composite calculation."""
    runs = [
        {
            "status": "PASSED",
            "mttd_seconds": 0.05,
            "time_to_recovery_seconds": 0.2,
            "error_budget_consumed_pct": 5.0,
        },
        {
            "status": "PASSED",
            "mttd_seconds": 0.08,
            "time_to_recovery_seconds": 0.3,
            "error_budget_consumed_pct": 10.0,
        },
        {
            "status": "PASSED",
            "mttd_seconds": 0.04,
            "time_to_recovery_seconds": 0.15,
            "error_budget_consumed_pct": 8.0,
        },
    ]
    card = ReliabilityScoringEngine.calculate_scorecard(runs)
    assert card.total_scenarios_run == 3
    assert card.passed_count == 3
    assert card.failed_count == 0
    assert card.detection_score == 100.0
    assert card.recovery_score == 100.0
    assert card.composite_score == 100.0
