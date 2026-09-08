"""Multi-window Burn Rate calculation engine to detect catastrophic or chronic SLO degradation without false alarms."""

import uuid
from datetime import UTC, datetime

from app.sre.schemas import BurnRateResponse, BurnRateWindow


def calculate_single_burn_rate(
    actual_error_rate: float,
    allowed_error_rate: float,
) -> float:
    """Compute burn rate = actual_error_rate / allowed_error_rate.

    Invariants:
    - burn_rate >= 0.0
    - If allowed_error_rate <= 0: returns 1000.0 if actual_error_rate > 0 else 0.0
    """
    actual = max(0.0, float(actual_error_rate))
    allowed = max(0.0, float(allowed_error_rate))

    if allowed <= 0.0:
        return 1000.0 if actual > 0.0 else 0.0

    return max(0.0, round(actual / allowed, 3))


def evaluate_burn_rate(
    slo_id: uuid.UUID,
    name: str,
    service: str,
    target: float,
    fast_window_seconds: int,
    fast_error_rate: float,
    slow_window_seconds: int,
    slow_error_rate: float,
    critical_fast_threshold: float = 14.4,
    critical_slow_threshold: float = 3.0,
    warning_fast_threshold: float = 7.2,
    warning_slow_threshold: float = 1.5,
) -> BurnRateResponse:
    """Evaluate dual-window burn rate against configurable thresholds.

    Dual-window burn rate alert criteria (SRE Handbook standard):
    - Critical burn triggered ONLY when both fast window and slow window exceed their thresholds.
      e.g., Fast (5m) > 14.4x AND Slow (1h) > 3.0x -> consumes 2% of budget in 1 hour.
    - Warning burn triggered when both exceed lower warning thresholds.
    """
    allowed_error_rate = max(0.0, 1.0 - float(target))

    fast_rate = calculate_single_burn_rate(fast_error_rate, allowed_error_rate)
    slow_rate = calculate_single_burn_rate(slow_error_rate, allowed_error_rate)

    is_critical = fast_rate >= critical_fast_threshold and slow_rate >= critical_slow_threshold
    is_warning = (
        not is_critical
        and fast_rate >= warning_fast_threshold
        and slow_rate >= warning_slow_threshold
    )

    fast_window = BurnRateWindow(
        window_name="fast",
        window_seconds=fast_window_seconds,
        actual_error_rate=round(fast_error_rate, 5),
        allowed_error_rate=round(allowed_error_rate, 5),
        burn_rate=fast_rate,
    )
    slow_window = BurnRateWindow(
        window_name="slow",
        window_seconds=slow_window_seconds,
        actual_error_rate=round(slow_error_rate, 5),
        allowed_error_rate=round(allowed_error_rate, 5),
        burn_rate=slow_rate,
    )

    return BurnRateResponse(
        slo_id=slo_id,
        name=name,
        service=service,
        fast_burn_window=fast_window,
        slow_burn_window=slow_window,
        is_critical_burn=is_critical,
        is_warning_burn=is_warning,
        evaluated_at=datetime.now(UTC),
    )
