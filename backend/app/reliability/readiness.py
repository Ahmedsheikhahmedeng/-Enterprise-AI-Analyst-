"""Production Readiness Evaluator assessing automated criteria and chaos evidence."""

from dataclasses import dataclass, field
from typing import Any

from app.reliability.enums import ReadinessDecision


@dataclass
class ReadinessEvaluationResult:
    """Detailed production readiness decision with factor breakdown."""

    decision: ReadinessDecision
    composite_score: float
    evaluation_factors: dict[str, Any]
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ProductionReadinessEvaluator:
    """Evaluates comprehensive production readiness evidence across the platform."""

    @classmethod
    def evaluate_readiness(
        cls,
        *,
        backend_tests_passed: bool = True,
        frontend_tests_passed: bool = True,
        security_gates_passed: bool = True,
        slo_breached: bool = False,
        error_budget_remaining_pct: float = 100.0,
        open_critical_incidents: int = 0,
        data_integrity_failures: int = 0,
        security_failures: int = 0,
        isolation_failures: int = 0,
        backup_verified: bool = True,
        worker_fleet_healthy: bool = True,
        llm_failover_verified: bool = True,
    ) -> ReadinessEvaluationResult:
        """Issue transparent READY / READY_WITH_WARNINGS / NOT_READY decision."""
        blockers: list[str] = []
        warnings: list[str] = []

        factors: dict[str, Any] = {
            "automated_tests": {
                "status": "PASS" if (backend_tests_passed and frontend_tests_passed) else "FAIL",
                "backend": backend_tests_passed,
                "frontend": frontend_tests_passed,
            },
            "security": {
                "status": "PASS" if security_gates_passed else "FAIL",
                "failures_count": security_failures,
            },
            "sre_slo": {
                "status": "FAIL"
                if slo_breached
                else ("WARN" if error_budget_remaining_pct < 20.0 else "PASS"),
                "error_budget_remaining_pct": error_budget_remaining_pct,
            },
            "incidents": {
                "status": "FAIL" if open_critical_incidents > 0 else "PASS",
                "open_critical_count": open_critical_incidents,
            },
            "data_integrity": {
                "status": "FAIL" if data_integrity_failures > 0 else "PASS",
                "failures_count": data_integrity_failures,
            },
            "tenant_isolation": {
                "status": "FAIL" if isolation_failures > 0 else "PASS",
                "failures_count": isolation_failures,
            },
            "infrastructure": {
                "status": "PASS"
                if (backup_verified and worker_fleet_healthy and llm_failover_verified)
                else "WARN",
                "backup_verified": backup_verified,
                "worker_fleet_healthy": worker_fleet_healthy,
                "llm_failover_verified": llm_failover_verified,
            },
        }

        # Hard Blockers (Zero Tolerance)
        if not backend_tests_passed or not frontend_tests_passed:
            blockers.append("Automated test suite has failing tests.")
        if not security_gates_passed or security_failures > 0:
            blockers.append(
                f"Security validation failed ({security_failures} security failures detected)."
            )
        if data_integrity_failures > 0:
            blockers.append(
                f"Data integrity compromise detected ({data_integrity_failures} failures)."
            )
        if isolation_failures > 0:
            blockers.append(
                f"Multi-tenant isolation breach detected ({isolation_failures} cross-tenant leaks)."
            )
        if open_critical_incidents > 0:
            blockers.append(
                f"{open_critical_incidents} unresolved SEV1/SEV2 incident(s) currently open."
            )
        if slo_breached or error_budget_remaining_pct <= 0.0:
            blockers.append("SLO objective breached; Error budget is completely exhausted.")

        # Non-blocking Warnings
        if error_budget_remaining_pct < 20.0 and error_budget_remaining_pct > 0.0:
            warnings.append(f"Error budget remaining is low ({error_budget_remaining_pct:.1f}%).")
        if not backup_verified:
            warnings.append("Last database backup verification is stale or unconfirmed.")
        if not worker_fleet_healthy:
            warnings.append("Worker fleet queue latency is elevated.")
        if not llm_failover_verified:
            warnings.append(
                "Secondary LLM fallback provider route has not been exercised recently."
            )

        # Determine Decision
        if blockers:
            decision = ReadinessDecision.NOT_READY
            score = 30.0
        elif warnings:
            decision = ReadinessDecision.READY_WITH_WARNINGS
            score = 80.0
        else:
            decision = ReadinessDecision.READY
            score = 100.0

        return ReadinessEvaluationResult(
            decision=decision,
            composite_score=score,
            evaluation_factors=factors,
            blockers=blockers,
            warnings=warnings,
        )
