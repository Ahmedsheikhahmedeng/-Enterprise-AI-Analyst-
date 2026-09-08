"""Unit tests for Runbook command safety scanning and Release Safety Gates."""

import pytest

from app.sre.enums import IncidentSeverityEnum, ReleaseGateDecisionEnum
from app.sre.gates import evaluate_release_safety
from app.sre.runbooks import UnsafeRunbookActionError, validate_runbook_safety


class TestRunbookSafetyValidation:
    """Validate detection and rejection of dangerous/destructive runbook instructions."""

    def test_safe_commands_permitted(self) -> None:
        safe_steps = [
            "Check database active connections: SELECT count(*) FROM pg_stat_activity WHERE state = 'active'",
            "Inspect system memory utilization using free -m or top",
            "Verify Redis queue length with LLEN jobs_queue",
            "Gracefully recycle idle background connection pool allocations",
        ]
        # Should not raise any error
        validate_runbook_safety(safe_steps)

    @pytest.mark.parametrize(
        "destructive_step",
        [
            "rm -rf /tmp/cache_store",
            "DROP TABLE audit_logs CASCADE",
            "DROP DATABASE platform_prod",
            "TRUNCATE user_sessions",
            "kill -9 4821",
            "DELETE FROM users",
        ],
    )
    def test_destructive_commands_rejected(self, destructive_step: str) -> None:
        with pytest.raises(UnsafeRunbookActionError) as exc_info:
            validate_runbook_safety([destructive_step])
        assert "forbidden destructive command pattern" in str(exc_info.value)


class TestReleaseSafetyGates:
    """Validate pre-deployment automated gate evaluation."""

    def test_release_gate_allow(self) -> None:
        decision, reasons = evaluate_release_safety(
            service="api_gateway",
            open_incidents=[],
            error_budget_remaining_pct=85.0,
            recent_error_rate=0.001,
        )
        assert decision == ReleaseGateDecisionEnum.ALLOW
        assert "All SRE health, incident, and error budget gates passed" in reasons[0]

    def test_release_gate_blocked_by_critical_incident(self) -> None:
        open_incidents = [
            {"id": "inc-1", "severity": IncidentSeverityEnum.SEV1.value, "status": "INVESTIGATING"}
        ]
        decision, reasons = evaluate_release_safety(
            service="database",
            open_incidents=open_incidents,
            error_budget_remaining_pct=90.0,
            recent_error_rate=0.001,
        )
        assert decision == ReleaseGateDecisionEnum.BLOCK
        assert any("active critical incident" in r for r in reasons)

    def test_release_gate_blocked_by_error_budget_exhaustion(self) -> None:
        decision, reasons = evaluate_release_safety(
            service="workers",
            open_incidents=[],
            error_budget_remaining_pct=5.0,  # Below 10.0% threshold
            recent_error_rate=0.001,
        )
        assert decision == ReleaseGateDecisionEnum.BLOCK
        assert any("Error budget remaining" in r for r in reasons)

    def test_release_gate_warning_for_moderate_incident(self) -> None:
        open_incidents = [
            {"id": "inc-2", "severity": IncidentSeverityEnum.SEV3.value, "status": "OPEN"}
        ]
        decision, reasons = evaluate_release_safety(
            service="reporting",
            open_incidents=open_incidents,
            error_budget_remaining_pct=80.0,
            recent_error_rate=0.002,
        )
        assert decision == ReleaseGateDecisionEnum.WARN
        assert any("SEV3" in r for r in reasons)
