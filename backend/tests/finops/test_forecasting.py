"""Tests for FinOps deterministic spend trajectory forecasting and overrun projections."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.finops.forecasting import ForecastingEngine


def test_deterministic_forecast_without_overrun() -> None:
    """Projected total is on track within budget limit."""
    org_id = uuid.uuid4()
    now = datetime.now(UTC)
    starts = now - timedelta(days=10)
    ends = now + timedelta(days=20)  # 30 day period, 10 days elapsed (1/3)
    # Spent $30 in 10 days -> $3/day velocity -> 30 days total = $90
    forecast = ForecastingEngine.generate_forecast(
        organization_id=org_id,
        actual_to_date=Decimal("30.0"),
        budget_limit=Decimal("100.0"),
        starts_at=starts,
        ends_at=ends,
        current_time=now,
    )
    assert forecast.actual_to_date == Decimal("30.0")
    assert forecast.forecasted_total == Decimal("90.0")
    assert forecast.budget_limit == Decimal("100.0")
    assert forecast.expected_overrun == Decimal("0.0")
    assert forecast.confidence >= 0.50


def test_forecast_detects_expected_overrun() -> None:
    """Detects and calculates expected financial overrun before period end."""
    org_id = uuid.uuid4()
    now = datetime.now(UTC)
    starts = now - timedelta(days=15)
    ends = now + timedelta(days=15)  # 30 day period, 15 days elapsed (1/2)
    # Spent $80 in 15 days on a $100 budget -> $5.333/day -> total = $160
    forecast = ForecastingEngine.generate_forecast(
        organization_id=org_id,
        actual_to_date=Decimal("80.0"),
        budget_limit=Decimal("100.0"),
        starts_at=starts,
        ends_at=ends,
        current_time=now,
    )
    assert forecast.forecasted_total == Decimal("160.0")
    assert forecast.expected_overrun == Decimal("60.0")  # $160 - $100


def test_forecast_zero_elapsed_time() -> None:
    """When called near start of period, projected total handles minimal elapsed time."""
    org_id = uuid.uuid4()
    now = datetime.now(UTC)
    starts = now
    ends = now + timedelta(days=30)

    forecast = ForecastingEngine.generate_forecast(
        organization_id=org_id,
        actual_to_date=Decimal("0.0"),
        budget_limit=Decimal("500.0"),
        starts_at=starts,
        ends_at=ends,
        current_time=now,
    )
    assert forecast.forecasted_total == Decimal("0.0")
    assert forecast.expected_overrun == Decimal("0.0")
