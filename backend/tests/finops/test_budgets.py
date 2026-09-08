"""Tests for FinOps budget engine, states, consumption, burn rate, and preflight checks."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.finops.budgets import BudgetEngine
from app.finops.enums import BudgetPeriod, BudgetScope, BudgetState
from app.finops.exceptions import BudgetExhaustedError
from app.finops.models import Budget, CostEvent


def test_budget_status_transitions() -> None:
    """Validate status transitions based on utilization of events within period."""
    now = datetime.now(UTC)
    budget = Budget(
        id="bg-1",
        organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        scope=BudgetScope.ORGANIZATION.value,
        period=BudgetPeriod.MONTHLY.value,
        limit_amount=Decimal("100.0"),
        warning_percent=80.0,
        critical_percent=95.0,
        enabled=True,
        starts_at=now - timedelta(days=15),
        ends_at=now + timedelta(days=15),
    )

    # 1. Spending (< 80%)
    res_spending = BudgetEngine.evaluate_consumption(
        budget,
        [CostEvent(id="e1", estimated_cost=Decimal("50.0"), timestamp=now)],
        as_of=now,
    )
    assert res_spending["state"] == BudgetState.SPENDING

    # 2. Warning (>= 80%, < 95%)
    res_warning = BudgetEngine.evaluate_consumption(
        budget,
        [CostEvent(id="e1", estimated_cost=Decimal("85.0"), timestamp=now)],
        as_of=now,
    )
    assert res_warning["state"] == BudgetState.WARNING

    # 3. Critical (>= 95%, < 100%)
    res_critical = BudgetEngine.evaluate_consumption(
        budget,
        [CostEvent(id="e1", estimated_cost=Decimal("97.0"), timestamp=now)],
        as_of=now,
    )
    assert res_critical["state"] == BudgetState.CRITICAL

    # 4. Exhausted (>= 100%)
    res_exhausted = BudgetEngine.evaluate_consumption(
        budget,
        [CostEvent(id="e1", estimated_cost=Decimal("105.0"), timestamp=now)],
        as_of=now,
    )
    assert res_exhausted["state"] == BudgetState.EXHAUSTED


def test_budget_consumption_non_negative_remaining() -> None:
    """Representation invariant: remaining amount must never be represented as negative."""
    now = datetime.now(UTC)
    budget = Budget(
        id="bg-1",
        organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        scope=BudgetScope.ORGANIZATION.value,
        period=BudgetPeriod.MONTHLY.value,
        limit_amount=Decimal("100.0"),
        warning_percent=80.0,
        critical_percent=95.0,
        enabled=True,
        starts_at=now - timedelta(days=15),
        ends_at=now + timedelta(days=15),
    )

    # Overspent case: spent $120 on $100 limit
    summary = BudgetEngine.evaluate_consumption(
        budget,
        [CostEvent(id="e1", estimated_cost=Decimal("120.0"), timestamp=now)],
        as_of=now,
    )
    assert summary["limit_amount"] == Decimal("100.0")
    assert summary["spent_amount"] == Decimal("120.0")
    assert summary["remaining_amount"] == Decimal("0.0")  # Invariant: Never negative
    assert summary["utilization_percent"] == 120.0
    assert summary["state"] == BudgetState.EXHAUSTED


def test_budget_burn_rate_faster_than_expected() -> None:
    """Detect when budget is burning faster than elapsed time ratio."""
    now = datetime.now(UTC)
    starts = now - timedelta(days=15)
    ends = now + timedelta(days=15)  # 50% period elapsed

    # 75% consumed ($75 / $100) at 50% elapsed -> burn_rate = 1.5 > 1.0
    rate = BudgetEngine.calculate_burn_rate(
        starts_at=starts,
        ends_at=ends,
        spent=Decimal("75.0"),
        limit=Decimal("100.0"),
        current_time=now,
    )
    assert rate > 1.0


def test_preflight_budget_check() -> None:
    """Preflight check raises BudgetExhaustedError when estimated cost breaches limit."""
    now = datetime.now(UTC)
    budget = Budget(
        id="bg-1",
        organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        scope=BudgetScope.ORGANIZATION.value,
        period=BudgetPeriod.MONTHLY.value,
        limit_amount=Decimal("100.0"),
        warning_percent=80.0,
        critical_percent=95.0,
        enabled=True,
        starts_at=now - timedelta(days=10),
        ends_at=now + timedelta(days=20),
    )

    # Case 1: Spent $90, estimate $5 -> total $95 <= $100 -> ALLOW (no exception)
    BudgetEngine.preflight_check(
        budget=budget,
        current_spent=Decimal("90.0"),
        estimated_operation_cost=Decimal("5.0"),
    )

    # Case 2: Spent $98, estimate $5 -> total $103 > $100 -> BLOCK (raises BudgetExhaustedError)
    with pytest.raises(BudgetExhaustedError) as exc_info:
        BudgetEngine.preflight_check(
            budget=budget,
            current_spent=Decimal("98.0"),
            estimated_operation_cost=Decimal("5.0"),
        )
    assert "would breach budget limit" in str(exc_info.value)
