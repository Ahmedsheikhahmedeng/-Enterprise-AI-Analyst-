"""Hierarchical budget evaluation, preflight reservation checks, and state lifecycle."""

from datetime import UTC, datetime
from decimal import Decimal

from app.finops.enums import BudgetState
from app.finops.exceptions import BudgetExhaustedError
from app.finops.models import Budget, CostEvent


class BudgetEngine:
    """Manages budget consumption, burn rate calculation, and hierarchical enforcement."""

    @classmethod
    def evaluate_consumption(
        cls,
        budget: Budget,
        events: list[CostEvent],
        as_of: datetime | None = None,
    ) -> dict[str, object]:
        """Compute spent, remaining, utilization percentage, state, and burn rate."""
        now = as_of or datetime.now(UTC)
        # Ensure budget starts_at and ends_at have timezone for comparison
        b_start = (
            budget.starts_at if budget.starts_at.tzinfo else budget.starts_at.replace(tzinfo=UTC)
        )
        b_end = (
            budget.ends_at
            if (budget.ends_at is None or budget.ends_at.tzinfo)
            else budget.ends_at.replace(tzinfo=UTC)
        )

        # Sum events within active budget window
        spent = Decimal("0.0")
        for ev in events:
            ev_ts = ev.timestamp if ev.timestamp.tzinfo else ev.timestamp.replace(tzinfo=UTC)
            if ev_ts >= b_start and (b_end is None or ev_ts <= b_end):
                spent += Decimal(str(ev.estimated_cost))

        limit = Decimal(str(budget.limit_amount))
        remaining = max(Decimal("0.0"), limit - spent)
        utilization = float((spent / limit) * 100) if limit > 0 else 100.0

        # Determine budget state
        if utilization >= 100.0:
            state = BudgetState.EXHAUSTED
        elif utilization >= budget.critical_percent:
            state = BudgetState.CRITICAL
        elif utilization >= budget.warning_percent:
            state = BudgetState.WARNING
        else:
            state = BudgetState.SPENDING

        # Burn rate calculation
        burn_rate = cls.calculate_burn_rate(b_start, b_end, spent, limit, now)

        return {
            "budget_id": budget.id,
            "limit_amount": limit,
            "spent_amount": spent,
            "remaining_amount": remaining,
            "utilization_percent": round(utilization, 2),
            "state": state,
            "burn_rate": round(burn_rate, 2),
        }

    @classmethod
    def preflight_check(
        cls,
        budget: Budget,
        current_spent: Decimal,
        estimated_operation_cost: Decimal,
    ) -> None:
        """Enforce that incoming estimated cost does not breach budget limit."""
        if not budget.enabled:
            return

        limit = Decimal(str(budget.limit_amount))
        projected = current_spent + estimated_operation_cost
        if projected > limit:
            raise BudgetExhaustedError(
                message=f"Preflight check rejected: Operation estimated cost (${estimated_operation_cost}) would breach budget limit (${limit}). Current spend: ${current_spent}.",
                budget_id=budget.id,
                limit_amount=str(limit),
                current_spent=str(current_spent),
            )

    @classmethod
    def calculate_burn_rate(
        cls,
        starts_at: datetime,
        ends_at: datetime | None,
        spent: Decimal,
        limit: Decimal,
        current_time: datetime,
    ) -> float:
        """Calculate spend velocity relative to elapsed time:
        burn_rate = actual_spend_rate / expected_spend_rate
        """
        if limit <= 0:
            return 1.0

        total_days = max(1.0, (ends_at - starts_at).total_seconds() / 86400.0) if ends_at else 30.0
        elapsed_days = max(
            0.01, min(total_days, (current_time - starts_at).total_seconds() / 86400.0)
        )

        expected_daily_spend = float(limit) / total_days
        actual_daily_spend = float(spent) / elapsed_days

        if expected_daily_spend <= 0:
            return 1.0

        return actual_daily_spend / expected_daily_spend
