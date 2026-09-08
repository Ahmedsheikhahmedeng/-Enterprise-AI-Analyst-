"""Unit tests for recovery timeline metrics and invariant validation."""

from datetime import UTC, datetime, timedelta

from app.reliability.recovery import RecoveryTimeline, RecoveryValidator


def test_recovery_timeline_mttd_and_mttr() -> None:
    """Verify calculation of MTTD, MTTA, MTTR, and time to recovery."""
    t0 = datetime(2026, 9, 7, 12, 0, 0, tzinfo=UTC)
    timeline = RecoveryTimeline(injected_at=t0)

    # Injected at 12:00:00, Detected at 12:00:05 (MTTD = 5s)
    timeline.detected_at = t0 + timedelta(seconds=5)
    assert timeline.mttd_seconds == 5.0

    # Acknowledged at 12:00:15 (MTTA = 10s)
    timeline.acknowledged_at = t0 + timedelta(seconds=15)
    assert timeline.mtta_seconds == 10.0

    # Recovered (infrastructure) at 12:00:25 (Time to recovery = 25s)
    timeline.recovered_at = t0 + timedelta(seconds=25)
    assert timeline.time_to_recovery_seconds == 25.0

    # Resolved (incident) at 12:00:45 (MTTR = 40s from detection)
    timeline.resolved_at = t0 + timedelta(seconds=45)
    assert timeline.mttr_seconds == 40.0


def test_recovery_validator_transitions() -> None:
    """Verify state transition validation: HEALTHY -> DEGRADED -> HEALTHY."""
    res_success = RecoveryValidator.evaluate_dependency_recovery(
        pre_fault_state="HEALTHY",
        in_fault_state="DEGRADED",
        post_fault_state="HEALTHY",
    )
    assert res_success["fault_detected"] is True
    assert res_success["fully_restored"] is True
    assert res_success["recovery_successful"] is True

    res_failed = RecoveryValidator.evaluate_dependency_recovery(
        pre_fault_state="HEALTHY",
        in_fault_state="UNHEALTHY",
        post_fault_state="DEGRADED",
    )
    assert res_failed["recovery_successful"] is False
