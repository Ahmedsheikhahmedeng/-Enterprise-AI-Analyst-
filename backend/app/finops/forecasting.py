"""Deterministic spend trajectory forecasting and budget overrun projection."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.finops.models import CostForecast


class ForecastingEngine:
    """Calculates deterministic spend trajectories and projected budget overruns."""

    @classmethod
    def generate_forecast(
        cls,
        organization_id: uuid.UUID,
        actual_to_date: Decimal,
        budget_limit: Decimal,
        starts_at: datetime,
        ends_at: datetime,
        current_time: datetime | None = None,
        period_name: str = "MONTHLY",
    ) -> CostForecast:
        """Linear velocity projection:
        daily_velocity = actual_to_date / elapsed_days
        forecasted_total = actual_to_date + (daily_velocity * remaining_days)
        expected_overrun = max(0, forecasted_total - budget_limit)
        """
        now = current_time or datetime.now(UTC)
        # Ensure timezone consistency
        now_tz = now if now.tzinfo else now.replace(tzinfo=UTC)
        s_tz = starts_at if starts_at.tzinfo else starts_at.replace(tzinfo=UTC)
        e_tz = ends_at if ends_at.tzinfo else ends_at.replace(tzinfo=UTC)

        total_days = max(1.0, (e_tz - s_tz).total_seconds() / 86400.0)
        elapsed_days = max(0.1, min(total_days, (now_tz - s_tz).total_seconds() / 86400.0))
        remaining_days = max(0.0, total_days - elapsed_days)

        daily_rate = actual_to_date / Decimal(str(elapsed_days))
        projected_additional = daily_rate * Decimal(str(remaining_days))
        forecasted_total = actual_to_date + projected_additional

        overrun = max(Decimal("0.0"), forecasted_total - budget_limit)

        # Confidence increases as period progresses toward 100%
        progress_ratio = min(1.0, elapsed_days / total_days)
        confidence = round(0.50 + (0.45 * progress_ratio), 2)

        return CostForecast(
            id=f"fc-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            period=period_name,
            actual_to_date=actual_to_date,
            forecasted_total=forecasted_total,
            budget_limit=budget_limit,
            expected_overrun=overrun,
            confidence=confidence,
            forecast_method="LINEAR_VELOCITY_PROJECTION",
        )
