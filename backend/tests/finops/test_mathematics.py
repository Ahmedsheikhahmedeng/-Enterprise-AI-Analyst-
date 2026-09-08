"""Property and mathematical invariant tests for FinOps calculations."""

from datetime import UTC, datetime
from decimal import Decimal

from app.finops.models import CostEvent, ModelPricing
from app.finops.pricing import ModelPricingRegistry
from app.finops.usage import CostLedgerEngine


def test_cost_non_negative_invariant() -> None:
    """Calculated cost must always be >= 0 across all valid inputs."""
    token_cases = [
        (0, 0, 0),
        (1, 0, 0),
        (100, 200, 50),
        (10_000_000, 5_000_000, 1_000_000),
    ]
    price_cases = [
        (Decimal("0.0"), Decimal("0.0"), Decimal("0.0")),
        (Decimal("1.50"), Decimal("5.00"), Decimal("0.75")),
        (Decimal("100.00"), Decimal("200.00"), Decimal("50.00")),
    ]

    for in_tok, out_tok, cach_tok in token_cases:
        for in_pr, out_pr, cach_pr in price_cases:
            pricing = ModelPricing(
                id="p-test",
                provider="p",
                model="m",
                version=1,
                input_price_per_1m=in_pr,
                output_price_per_1m=out_pr,
                cached_input_price_per_1m=cach_pr,
            )
            calc = ModelPricingRegistry.calculate_cost(
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_tokens=cach_tok,
                pricing=pricing,
            )
            assert calc.total_cost >= Decimal("0.0")


def test_huge_token_counts_overflow_protection() -> None:
    """Extreme token volumes (e.g. 50 billion tokens) calculate accurately without overflow."""
    huge_input = 50_000_000_000
    huge_output = 10_000_000_000
    pricing = ModelPricing(
        id="p-huge",
        provider="openai",
        model="gpt-4o",
        version=1,
        input_price_per_1m=Decimal("2.50"),
        output_price_per_1m=Decimal("10.00"),
    )
    calc = ModelPricingRegistry.calculate_cost(
        input_tokens=huge_input,
        output_tokens=huge_output,
        cached_tokens=0,
        pricing=pricing,
    )
    # (50,000 * 2.50) + (10,000 * 10.00) = 125,000 + 100,000 = $225,000
    assert calc.total_cost == Decimal("225000.00000000")


def test_attribution_completeness_ratio() -> None:
    """Completeness ratio strictly bounded between 0.0% and 100.0%."""
    now = datetime.now(UTC)
    events_full = [
        CostEvent(id="e1", organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", timestamp=now)
    ]
    events_none = [CostEvent(id="e2", organization_id=None, timestamp=now)]

    assert CostLedgerEngine.calculate_attribution_completeness(events_full) == 100.0
    assert CostLedgerEngine.calculate_attribution_completeness(events_none) == 0.0
    assert CostLedgerEngine.calculate_attribution_completeness(events_full + events_none) == 50.0
    assert CostLedgerEngine.calculate_attribution_completeness([]) == 100.0


def test_wasted_cost_calculation() -> None:
    """Wasted cost strictly aggregates failed and retry attempts."""
    now = datetime.now(UTC)
    events = [
        CostEvent(
            id="e1", estimated_cost=Decimal("0.05"), is_failed=True, is_retry=False, timestamp=now
        ),
        CostEvent(
            id="e2", estimated_cost=Decimal("0.05"), is_failed=False, is_retry=True, timestamp=now
        ),
        CostEvent(
            id="e3", estimated_cost=Decimal("0.10"), is_failed=False, is_retry=False, timestamp=now
        ),
    ]
    wasted = CostLedgerEngine.calculate_wasted_cost(events)
    assert wasted == Decimal("0.10")
