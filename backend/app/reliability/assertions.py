"""Verification Assertions for Data Integrity, Tenant Isolation, and Safety Guarantees."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.reliability.enums import AssertionStatus, AssertionType


@dataclass
class AssertionResult:
    """Outcome of an invariant assertion check."""

    assertion_type: AssertionType
    status: AssertionStatus
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_passed(self) -> bool:
        return self.status == AssertionStatus.PASSED


class ReliabilityAssertionEngine:
    """Evaluates strict invariants during and post-chaos execution."""

    @staticmethod
    def assert_data_integrity(
        *,
        corrupted_records: int = 0,
        orphaned_chunks: int = 0,
        checkpoint_consistent: bool = True,
    ) -> AssertionResult:
        """Verify no database state corruption or orphaned records exist."""
        passed = (corrupted_records == 0) and (orphaned_chunks == 0) and checkpoint_consistent
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.DATA_INTEGRITY,
            status=status,
            description="Verify database referential integrity, checkpoints, and absence of corrupted rows.",
            evidence={
                "corrupted_records": corrupted_records,
                "orphaned_chunks": orphaned_chunks,
                "checkpoint_consistent": checkpoint_consistent,
            },
        )

    @staticmethod
    def assert_tenant_isolation(
        *,
        cross_tenant_data_leaked: bool = False,
        tenant_b_affected_by_a: bool = False,
        tenant_b_success_rate: float = 1.0,
    ) -> AssertionResult:
        """Verify Tenant B was completely unaffected by Tenant A fault injection."""
        passed = (
            (not cross_tenant_data_leaked)
            and (not tenant_b_affected_by_a)
            and (tenant_b_success_rate >= 0.99)
        )
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.TENANT_ISOLATION,
            status=status,
            description="Verify multi-tenant isolation barriers remain rigid under failure conditions.",
            evidence={
                "cross_tenant_data_leaked": cross_tenant_data_leaked,
                "tenant_b_affected_by_a": tenant_b_affected_by_a,
                "tenant_b_success_rate": tenant_b_success_rate,
            },
        )

    @staticmethod
    def assert_security_preserved(
        *,
        unauthenticated_requests_allowed: int = 0,
        rbac_bypassed: bool = False,
    ) -> AssertionResult:
        """Verify that degradation never causes fail-open security bypass."""
        passed = (unauthenticated_requests_allowed == 0) and (not rbac_bypassed)
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.SECURITY_PRESERVED,
            status=status,
            description="Verify authentication and RBAC boundaries cannot be bypassed during degraded modes.",
            evidence={
                "unauthenticated_requests_allowed": unauthenticated_requests_allowed,
                "rbac_bypassed": rbac_bypassed,
            },
        )

    @staticmethod
    def assert_no_leaked_tasks(
        *,
        dangling_locks: int = 0,
        unreclaimed_jobs: int = 0,
    ) -> AssertionResult:
        """Verify background worker leases and queue tasks are cleanly reclaimed or finalized."""
        passed = (dangling_locks == 0) and (unreclaimed_jobs == 0)
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.NO_LEAKED_TASKS,
            status=status,
            description="Verify worker leases, distributed locks, and queue items are completely cleaned up.",
            evidence={
                "dangling_locks": dangling_locks,
                "unreclaimed_jobs": unreclaimed_jobs,
            },
        )

    @staticmethod
    def assert_retry_storm_protection(
        *,
        actual_retries: int,
        max_allowed_retries: int = 3,
        backoff_applied: bool = True,
    ) -> AssertionResult:
        """Verify retries are strictly bounded and employ backoff."""
        passed = (actual_retries <= max_allowed_retries) and backoff_applied
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.RETRY_STORM_PROTECTION,
            status=status,
            description="Verify retry storm protection bounded downstream calls to max attempts.",
            evidence={
                "actual_retries": actual_retries,
                "max_allowed_retries": max_allowed_retries,
                "backoff_applied": backoff_applied,
            },
        )

    @staticmethod
    def assert_circuit_breaker(
        *,
        circuit_tripped: bool,
        subsequent_calls_blocked: bool,
    ) -> AssertionResult:
        """Verify circuit breaker opens upon error threshold and prevents downstream overload."""
        passed = circuit_tripped and subsequent_calls_blocked
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.CIRCUIT_BREAKER_ACTIVE,
            status=status,
            description="Verify circuit breaker transitions to OPEN and sheds load.",
            evidence={
                "circuit_tripped": circuit_tripped,
                "subsequent_calls_blocked": subsequent_calls_blocked,
            },
        )

    @staticmethod
    def assert_timeout_budget(
        *,
        elapsed_ms: float,
        deadline_ms: float,
    ) -> AssertionResult:
        """Verify nested sub-calls honor parent timeout deadline."""
        passed = elapsed_ms <= (deadline_ms + 150.0)  # allowance for thread scheduling
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.TIMEOUT_BUDGET_HONORED,
            status=status,
            description="Verify overall request deadline was honored and did not hang indefinitely.",
            evidence={
                "elapsed_ms": elapsed_ms,
                "deadline_ms": deadline_ms,
            },
        )

    @staticmethod
    def assert_graceful_degradation(
        *,
        raw_exception_exposed: bool = False,
        controlled_status_code: int = 503,
        fallback_used: bool = False,
    ) -> AssertionResult:
        """Verify client received structured error or fallback response instead of crash."""
        passed = (not raw_exception_exposed) and (controlled_status_code in (200, 206, 503, 429))
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.GRACEFUL_DEGRADATION,
            status=status,
            description="Verify system degraded gracefully without unhandled exceptions or crash.",
            evidence={
                "raw_exception_exposed": raw_exception_exposed,
                "controlled_status_code": controlled_status_code,
                "fallback_used": fallback_used,
            },
        )

    @staticmethod
    def assert_recovery_success(
        *,
        dependency_healthy: bool,
        alert_resolved: bool,
    ) -> AssertionResult:
        """Verify dependency returned to green and firing alerts resolved."""
        passed = dependency_healthy and alert_resolved
        status = AssertionStatus.PASSED if passed else AssertionStatus.FAILED
        return AssertionResult(
            assertion_type=AssertionType.RECOVERY_SUCCESS,
            status=status,
            description="Verify complete return to healthy baseline and automatic alert resolution.",
            evidence={
                "dependency_healthy": dependency_healthy,
                "alert_resolved": alert_resolved,
            },
        )
