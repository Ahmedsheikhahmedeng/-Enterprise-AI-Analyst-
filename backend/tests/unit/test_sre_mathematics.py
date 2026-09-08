"""Unit tests for SRE mathematical invariants, SLIs, Error Budgets, and Burn Rates."""

import uuid

from app.sre.burn_rate import calculate_single_burn_rate, evaluate_burn_rate
from app.sre.enums import SLOStatusEnum
from app.sre.error_budget import compute_error_budget
from app.sre.sli import (
    compute_availability,
    compute_error_rate,
    compute_latency_percentiles,
    compute_queue_health,
    compute_saturation,
    compute_worker_health,
)


class TestSLIMathematics:
    """Mathematical properties and edge cases of Service Level Indicators."""

    def test_availability_invariants(self) -> None:
        # Standard ratio
        assert compute_availability(999, 1000) == 0.999

        # Invariant 0.0 <= A <= 1.0
        assert compute_availability(1000, 1000) == 1.0
        assert compute_availability(0, 1000) == 0.0
        assert compute_availability(1200, 1000) == 1.0  # Clamped

        # Zero requests edge case: should return 1.0 (no errors observed)
        assert compute_availability(0, 0) == 1.0
        assert compute_availability(5, -1) == 1.0

    def test_error_rate_invariants(self) -> None:
        # Standard ratio
        assert compute_error_rate(5, 1000) == 0.005

        # Invariant 0.0 <= E <= 1.0
        assert compute_error_rate(0, 1000) == 0.0
        assert compute_error_rate(1000, 1000) == 1.0
        assert compute_error_rate(1500, 1000) == 1.0  # Clamped

        # Zero requests edge case: returns 0.0
        assert compute_error_rate(0, 0) == 0.0
        assert compute_error_rate(5, -10) == 0.0

    def test_latency_percentiles_ordering(self) -> None:
        latencies = [10.0, 20.0, 30.0, 50.0, 80.0, 100.0, 200.0, 500.0, 1000.0]
        percentiles = compute_latency_percentiles(latencies)

        assert percentiles["p50"] <= percentiles["p95"] <= percentiles["p99"]
        assert percentiles["p50"] > 0.0

        # Empty list returns zeroes
        empty_p = compute_latency_percentiles([])
        assert empty_p == {"p50": 0.0, "p95": 0.0, "p99": 0.0}

        # Single element
        single_p = compute_latency_percentiles([42.5])
        assert single_p == {"p50": 42.5, "p95": 42.5, "p99": 42.5}

    def test_saturation_clamping(self) -> None:
        assert compute_saturation(50.0, 100.0) == 0.5
        assert compute_saturation(150.0, 100.0) == 1.0
        assert compute_saturation(0.0, 100.0) == 0.0
        assert compute_saturation(10.0, 0.0) == 0.0

    def test_queue_and_worker_health(self) -> None:
        q_health = compute_queue_health(
            pending_jobs=50, lag_seconds=5.2, failed_jobs=2, total_processed=98
        )
        assert q_health["is_lagging"] is False
        assert q_health["failure_rate"] == 0.02

        w_health = compute_worker_health(
            successful_tasks=95, failed_tasks=5, heartbeat_age_seconds=10.0
        )
        assert w_health["is_alive"] is True
        assert w_health["is_healthy"] is True
        assert w_health["success_rate"] == 0.95


class TestErrorBudgetMathematics:
    """Mathematical properties of the Error Budget Engine."""

    def test_healthy_error_budget(self) -> None:
        slo_id = uuid.uuid4()
        # 99.9% target -> 0.1% (0.001) total budget
        budget = compute_error_budget(
            slo_id=slo_id,
            name="API Availability",
            service="api",
            target=0.999,
            window_seconds=86400,
            actual_error_rate=0.0002,  # 0.02% error -> 20% consumed, 80% remaining
        )
        assert budget.status == SLOStatusEnum.HEALTHY
        assert budget.budget_total == 0.001
        assert budget.budget_consumed == 0.0002
        assert budget.budget_remaining == 0.0008
        assert budget.budget_remaining_percent == 80.0

    def test_at_risk_error_budget(self) -> None:
        slo_id = uuid.uuid4()
        # Consumed 0.00085 out of 0.001 -> 15% remaining (< 20%) -> AT_RISK
        budget = compute_error_budget(
            slo_id=slo_id,
            name="API Availability",
            service="api",
            target=0.999,
            window_seconds=86400,
            actual_error_rate=0.00085,
        )
        assert budget.status == SLOStatusEnum.AT_RISK
        assert budget.budget_remaining_percent == 15.0

    def test_breached_error_budget(self) -> None:
        slo_id = uuid.uuid4()
        # Consumed 0.002 out of 0.001 -> 0% remaining -> BREACHED
        budget = compute_error_budget(
            slo_id=slo_id,
            name="API Availability",
            service="api",
            target=0.999,
            window_seconds=86400,
            actual_error_rate=0.002,
        )
        assert budget.status == SLOStatusEnum.BREACHED
        assert budget.budget_remaining == 0.0
        assert budget.budget_remaining_percent == 0.0

    def test_non_negative_invariants(self) -> None:
        slo_id = uuid.uuid4()
        budget = compute_error_budget(
            slo_id=slo_id,
            name="Invariant Test",
            service="test",
            target=0.99,
            window_seconds=3600,
            actual_error_rate=0.50,  # 50x over budget
        )
        assert budget.budget_remaining >= 0.0
        assert 0.0 <= budget.budget_remaining_percent <= 100.0


class TestBurnRateMathematics:
    """Mathematical properties of the Multi-Window Burn Rate Engine."""

    def test_single_burn_rate_calculation(self) -> None:
        # Target: 99.9% (allowed: 0.001)
        # Actual error rate: 0.0144 (14.4x burn rate)
        rate = calculate_single_burn_rate(actual_error_rate=0.0144, allowed_error_rate=0.001)
        assert rate == 14.4

        # Zero errors
        assert calculate_single_burn_rate(0.0, 0.001) == 0.0

        # Zero allowed errors edge case
        assert calculate_single_burn_rate(0.01, 0.0) == 1000.0
        assert calculate_single_burn_rate(0.0, 0.0) == 0.0

    def test_multi_window_burn_rate_policies(self) -> None:
        slo_id = uuid.uuid4()

        # Case 1: Fast spike only (transient 5m spike, but 1h slow window is healthy) -> NOT CRITICAL
        result = evaluate_burn_rate(
            slo_id=slo_id,
            name="API Availability",
            service="api",
            target=0.999,
            fast_window_seconds=300,
            fast_error_rate=0.015,  # 15x burn
            slow_window_seconds=3600,
            slow_error_rate=0.001,  # 1x burn (< 3.0x threshold)
        )
        assert result.is_critical_burn is False
        assert result.is_warning_burn is False

        # Case 2: Catastrophic dual-window breach (both fast > 14.4x and slow > 3.0x) -> CRITICAL BURN
        result_crit = evaluate_burn_rate(
            slo_id=slo_id,
            name="API Availability",
            service="api",
            target=0.999,
            fast_window_seconds=300,
            fast_error_rate=0.020,  # 20x burn
            slow_window_seconds=3600,
            slow_error_rate=0.004,  # 4x burn
        )
        assert result_crit.is_critical_burn is True

        # Case 3: Moderate sustained degradation -> WARNING BURN
        result_warn = evaluate_burn_rate(
            slo_id=slo_id,
            name="API Availability",
            service="api",
            target=0.999,
            fast_window_seconds=300,
            fast_error_rate=0.008,  # 8x burn (>= 7.2x)
            slow_window_seconds=3600,
            slow_error_rate=0.002,  # 2x burn (>= 1.5x)
        )
        assert result_warn.is_warning_burn is True
        assert result_warn.is_critical_burn is False
