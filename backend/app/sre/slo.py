"""SLO evaluation orchestrator matching SLI observations against target objectives and windows."""

import uuid
from datetime import UTC, datetime

from app.sre.burn_rate import evaluate_burn_rate
from app.sre.enums import SLOStatusEnum
from app.sre.error_budget import compute_error_budget
from app.sre.schemas import SLOEvaluationResult

SUPPORTED_WINDOWS = {
    "1h": 3600,
    "6h": 21600,
    "24h": 86400,
    "7d": 604800,
    "30d": 2592000,
}


def evaluate_slo_compliance(
    slo_id: uuid.UUID,
    name: str,
    service: str,
    target_value: float,
    window_seconds: int,
    actual_value: float,
    fast_window_error_rate: float | None = None,
    slow_window_error_rate: float | None = None,
    warning_threshold: float = 0.995,
    critical_threshold: float = 0.990,
) -> SLOEvaluationResult:
    """Evaluate an SLO against current window metrics, error budget, and burn rate."""
    actual_error_rate = max(0.0, 1.0 - float(actual_value))
    fast_err = fast_window_error_rate if fast_window_error_rate is not None else actual_error_rate
    slow_err = slow_window_error_rate if slow_window_error_rate is not None else actual_error_rate

    error_budget = compute_error_budget(
        slo_id=slo_id,
        name=name,
        service=service,
        target=target_value,
        window_seconds=window_seconds,
        actual_error_rate=actual_error_rate,
        warning_threshold=warning_threshold,
        critical_threshold=critical_threshold,
    )

    burn_rate = evaluate_burn_rate(
        slo_id=slo_id,
        name=name,
        service=service,
        target=target_value,
        fast_window_seconds=min(300, max(60, window_seconds // 24)),
        fast_error_rate=fast_err,
        slow_window_seconds=min(3600, max(300, window_seconds // 6)),
        slow_error_rate=slow_err,
    )

    # Determine overall SLO status
    if error_budget.status == SLOStatusEnum.BREACHED or burn_rate.is_critical_burn:
        status = SLOStatusEnum.BREACHED
    elif error_budget.status == SLOStatusEnum.AT_RISK or burn_rate.is_warning_burn:
        status = SLOStatusEnum.AT_RISK
    else:
        status = SLOStatusEnum.HEALTHY

    return SLOEvaluationResult(
        slo_id=slo_id,
        name=name,
        service=service,
        target_value=round(target_value, 4),
        actual_value=round(actual_value, 4),
        window_seconds=window_seconds,
        status=status,
        error_budget=error_budget,
        burn_rate=burn_rate,
        evaluated_at=datetime.now(UTC),
    )
