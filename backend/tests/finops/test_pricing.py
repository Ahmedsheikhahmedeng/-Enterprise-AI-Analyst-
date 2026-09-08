"""Tests for FinOps model pricing registry, deterministic formulas, and versioning."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.finops.models import ModelPricing
from app.finops.pricing import CANONICAL_PRICING, ModelPricingRegistry


def test_deterministic_cost_calculation() -> None:
    """Validate standard deterministic cost formula without floating-point inaccuracies."""
    # 1,000,000 input tokens at $5.00/1M = $5.00
    # 500,000 output tokens at $15.00/1M = $7.50
    # 200,000 cached tokens at $2.50/1M = $0.50
    # Total = $13.00
    pricing = ModelPricing(
        id="p-1",
        provider="test-ai",
        model="gpt-4o",
        version=1,
        input_price_per_1m=Decimal("5.00"),
        output_price_per_1m=Decimal("15.00"),
        cached_input_price_per_1m=Decimal("2.50"),
    )
    result = ModelPricingRegistry.calculate_cost(
        input_tokens=1_000_000,
        output_tokens=500_000,
        cached_tokens=200_000,
        pricing=pricing,
    )
    assert result.total_cost == Decimal("13.00000000")
    assert result.input_cost == Decimal("5.00000000")
    assert result.output_cost == Decimal("7.50000000")
    assert result.cached_cost == Decimal("0.50000000")
    assert result.is_pricing_known is True


def test_cost_calculation_zero_tokens() -> None:
    """Zero tokens should deterministically yield zero cost."""
    pricing = ModelPricing(
        id="p-1",
        provider="test-ai",
        model="gpt-4o",
        version=1,
        input_price_per_1m=Decimal("5.00"),
        output_price_per_1m=Decimal("15.00"),
    )
    result = ModelPricingRegistry.calculate_cost(
        input_tokens=0,
        output_tokens=0,
        cached_tokens=0,
        pricing=pricing,
    )
    assert result.total_cost == Decimal("0.00000000")


def test_cost_calculation_no_cached_price() -> None:
    """When cached price is None, cached tokens use standard input price."""
    pricing = ModelPricing(
        id="p-1",
        provider="test-ai",
        model="gpt-4o",
        version=1,
        input_price_per_1m=Decimal("10.00"),
        output_price_per_1m=Decimal("30.00"),
        cached_input_price_per_1m=None,
    )
    result = ModelPricingRegistry.calculate_cost(
        input_tokens=100_000,
        output_tokens=50_000,
        cached_tokens=25_000,
        pricing=pricing,
    )
    # (100000/1M * 10) + (50000/1M * 30) + (25000/1M * 10) = 1.0 + 1.5 + 0.25 = 2.75
    assert result.total_cost == Decimal("2.75000000")


def test_canonical_pricing_registry() -> None:
    """Canonical initial pricing list contains expected models."""
    models = {p["model"] for p in CANONICAL_PRICING}
    assert "gpt-4o" in models
    assert "gpt-4o-mini" in models
    assert "claude-3-5-sonnet" in models


def test_pricing_versioning_and_effective_dates() -> None:
    """Registry selects active price version matching the timestamp."""
    now = datetime.now(UTC)

    v1 = ModelPricing(
        id="p-v1",
        provider="custom",
        model="llm-v1",
        version=1,
        input_price_per_1m=Decimal("1.00"),
        output_price_per_1m=Decimal("2.00"),
        effective_from=now - timedelta(days=30),
        effective_until=now - timedelta(days=1),
    )
    v2 = ModelPricing(
        id="p-v2",
        provider="custom",
        model="llm-v1",
        version=2,
        input_price_per_1m=Decimal("0.80"),
        output_price_per_1m=Decimal("1.60"),
        effective_from=now - timedelta(days=1),
        effective_until=None,
    )
    records = [v1, v2]

    # Query for 10 days ago -> should get v1
    hist_price = ModelPricingRegistry.resolve_pricing(
        "custom", "llm-v1", timestamp=now - timedelta(days=10), pricing_records=records
    )
    assert hist_price is not None
    assert hist_price.version == 1
    assert hist_price.input_price_per_1m == Decimal("1.00")

    # Query for now -> should get v2
    current_price = ModelPricingRegistry.resolve_pricing(
        "custom", "llm-v1", timestamp=now, pricing_records=records
    )
    assert current_price is not None
    assert current_price.version == 2
    assert current_price.input_price_per_1m == Decimal("0.80")


def test_unknown_pricing_does_not_crash() -> None:
    """Missing model pricing safely returns unknown result without crashing."""
    result = ModelPricingRegistry.calculate_cost(
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=0,
        pricing=None,
    )
    assert result.total_cost == Decimal("0.0")
    assert result.is_pricing_known is False
    assert result.pricing_version == 0
