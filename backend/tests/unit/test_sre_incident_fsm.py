"""Unit tests for Incident Lifecycle Finite State Machine (FSM), MTTA, and MTTR calculations."""

from datetime import UTC, datetime, timedelta

import pytest

from app.sre.enums import IncidentStatusEnum
from app.sre.incidents import (
    InvalidIncidentTransitionError,
    aggregate_mttr_metrics,
    calculate_mtta_seconds,
    calculate_mttr_seconds,
    validate_incident_transition,
)


class TestIncidentFSM:
    """Validate strict state transition rules."""

    def test_valid_forward_transitions(self) -> None:
        # Standard forward lifecycle
        validate_incident_transition(IncidentStatusEnum.OPEN, IncidentStatusEnum.ACKNOWLEDGED)
        validate_incident_transition(
            IncidentStatusEnum.ACKNOWLEDGED, IncidentStatusEnum.INVESTIGATING
        )
        validate_incident_transition(IncidentStatusEnum.INVESTIGATING, IncidentStatusEnum.MITIGATED)
        validate_incident_transition(IncidentStatusEnum.MITIGATED, IncidentStatusEnum.RESOLVED)
        validate_incident_transition(IncidentStatusEnum.RESOLVED, IncidentStatusEnum.CLOSED)

        # Idempotent self-transitions
        validate_incident_transition(IncidentStatusEnum.OPEN, IncidentStatusEnum.OPEN)
        validate_incident_transition(
            IncidentStatusEnum.INVESTIGATING, IncidentStatusEnum.INVESTIGATING
        )

        # Mitigation failed -> return to investigation
        validate_incident_transition(IncidentStatusEnum.MITIGATED, IncidentStatusEnum.INVESTIGATING)

        # Fast-track resolution
        validate_incident_transition(IncidentStatusEnum.OPEN, IncidentStatusEnum.RESOLVED)

    def test_forbidden_terminal_transitions(self) -> None:
        # CLOSED is terminal: no transition allowed
        with pytest.raises(InvalidIncidentTransitionError) as exc_info:
            validate_incident_transition(IncidentStatusEnum.CLOSED, IncidentStatusEnum.OPEN)
        assert "Illegal incident transition" in str(exc_info.value)

        with pytest.raises(InvalidIncidentTransitionError):
            validate_incident_transition(
                IncidentStatusEnum.CLOSED, IncidentStatusEnum.INVESTIGATING
            )

        with pytest.raises(InvalidIncidentTransitionError):
            validate_incident_transition(IncidentStatusEnum.CLOSED, IncidentStatusEnum.RESOLVED)

    def test_forbidden_backward_transitions(self) -> None:
        # Cannot revert from RESOLVED to OPEN
        with pytest.raises(InvalidIncidentTransitionError):
            validate_incident_transition(IncidentStatusEnum.RESOLVED, IncidentStatusEnum.OPEN)

        with pytest.raises(InvalidIncidentTransitionError):
            validate_incident_transition(
                IncidentStatusEnum.RESOLVED, IncidentStatusEnum.INVESTIGATING
            )

        # Cannot revert from MITIGATED directly to OPEN
        with pytest.raises(InvalidIncidentTransitionError):
            validate_incident_transition(IncidentStatusEnum.MITIGATED, IncidentStatusEnum.OPEN)


class TestMTTAAndMTTRMetrics:
    """Validate Mean Time To Acknowledge and Mean Time To Resolve metrics."""

    def test_mtta_calculation(self) -> None:
        t0 = datetime(2026, 9, 7, 10, 0, 0, tzinfo=UTC)
        t_ack = datetime(2026, 9, 7, 10, 5, 0, tzinfo=UTC)  # 5 minutes = 300s

        mtta = calculate_mtta_seconds(t0, t_ack)
        assert mtta == 300.0

        # Unacknowledged returns None
        assert calculate_mtta_seconds(t0, None) is None

        # Negative edge case (clock drift where ack is before opened)
        assert calculate_mtta_seconds(t0, t0 - timedelta(seconds=10)) is None

    def test_mttr_calculation(self) -> None:
        t0 = datetime(2026, 9, 7, 10, 0, 0, tzinfo=UTC)
        t_res = datetime(2026, 9, 7, 10, 45, 0, tzinfo=UTC)  # 45 minutes = 2700s

        mttr = calculate_mttr_seconds(t0, t_res)
        assert mttr == 2700.0
        assert calculate_mttr_seconds(t0, None) is None

    def test_aggregate_mttr_metrics(self) -> None:
        # Durations in seconds: 600, 1200, 1800, 2400, 3000
        durations = [600.0, 1200.0, 1800.0, 2400.0, 3000.0]
        agg = aggregate_mttr_metrics(durations)

        assert agg["average"] == 1800.0
        assert agg["median"] == 1800.0
        assert agg["p95"] == 3000.0

        # Empty durations
        empty_agg = aggregate_mttr_metrics([])
        assert empty_agg["average"] is None
        assert empty_agg["median"] is None
        assert empty_agg["p95"] is None
