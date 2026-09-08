"""Error budget computation engine enforcing deterministic accounting and non-negative boundaries."""

import uuid
from datetime import UTC, datetime

from app.sre.enums import SLOStatusEnum
from app.sre.schemas import ErrorBudgetResponse


def compute_error_budget(
    slo_id: uuid.UUID,
    name: str,
    service: str,
    target: float,
    window_seconds: int,
    actual_error_rate: float,
    warning_threshold: float | None = None,
    critical_threshold: float | None = None,
) -> ErrorBudgetResponse:
    """Calculate error budget and consumption status.

    Formula:
    - budget_total = 1.0 - target
    - budget_consumed = actual_error_rate (clamped >= 0.0)
    - budget_remaining = max(0.0, budget_total - budget_consumed)
    - budget_remaining_percent = (budget_remaining / budget_total) * 100.0 (clamped [0.0, 100.0])

    Status:
    - BREACHED: budget_consumed >= budget_total (budget_remaining == 0.0)
    - AT_RISK: budget_remaining_percent < 20.0% or actual_error_rate > (budget_total * 0.8)
    - HEALTHY: normal operation within budget
    """
    # Defensive target clamping
    target = max(0.0, min(1.0, float(target)))
    budget_total = max(0.0, 1.0 - target)

    budget_consumed = max(0.0, float(actual_error_rate))
    budget_remaining = max(0.0, budget_total - budget_consumed)

    if budget_total > 0.0:
        budget_remaining_percent = max(0.0, min(100.0, (budget_remaining / budget_total) * 100.0))
    else:
        # 100% target -> 0 budget total allowed
        budget_remaining_percent = 100.0 if budget_consumed == 0.0 else 0.0

    # Determine status
    if (
        budget_remaining <= 0.0
        and budget_total > 0.0
        or critical_threshold is not None
        and (1.0 - budget_consumed) < critical_threshold
    ):
        status = SLOStatusEnum.BREACHED
    elif budget_remaining_percent < 20.0 or (
        warning_threshold is not None and (1.0 - budget_consumed) < warning_threshold
    ):
        status = SLOStatusEnum.AT_RISK
    else:
        status = SLOStatusEnum.HEALTHY

    return ErrorBudgetResponse(
        slo_id=slo_id,
        name=name,
        service=service,
        target=round(target, 4),
        window_seconds=window_seconds,
        budget_total=round(budget_total, 6),
        budget_consumed=round(budget_consumed, 6),
        budget_remaining=round(budget_remaining, 6),
        budget_remaining_percent=round(budget_remaining_percent, 2),
        status=status,
        calculated_at=datetime.now(UTC),
    )
