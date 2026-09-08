"""Model pricing registry, deterministic token cost calculation, and version resolution."""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from app.finops.models import ModelPricing


class CostCalculationResult(NamedTuple):
    total_cost: Decimal
    input_cost: Decimal
    output_cost: Decimal
    cached_cost: Decimal
    pricing_version: int
    is_pricing_known: bool


# Canonical initial baseline estimates (clearly declared as CONFIGURED_ESTIMATE, not authoritative invoices)
CANONICAL_PRICING: list[dict[str, object]] = [
    {
        "id": "price-gpt-4o-v1",
        "provider": "openai",
        "model": "gpt-4o",
        "version": 1,
        "input_price_per_1m": Decimal("5.0000"),
        "output_price_per_1m": Decimal("15.0000"),
        "cached_input_price_per_1m": Decimal("2.5000"),
        "currency": "USD",
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
        "effective_until": None,
        "source": "CONFIGURED_ESTIMATE",
    },
    {
        "id": "price-gpt-4o-mini-v1",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "version": 1,
        "input_price_per_1m": Decimal("0.1500"),
        "output_price_per_1m": Decimal("0.6000"),
        "cached_input_price_per_1m": Decimal("0.0750"),
        "currency": "USD",
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
        "effective_until": None,
        "source": "CONFIGURED_ESTIMATE",
    },
    {
        "id": "price-claude-3-5-sonnet-v1",
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "version": 1,
        "input_price_per_1m": Decimal("3.0000"),
        "output_price_per_1m": Decimal("15.0000"),
        "cached_input_price_per_1m": Decimal("0.3000"),
        "currency": "USD",
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
        "effective_until": None,
        "source": "CONFIGURED_ESTIMATE",
    },
    {
        "id": "price-gemini-1-5-pro-v1",
        "provider": "google",
        "model": "gemini-1.5-pro",
        "version": 1,
        "input_price_per_1m": Decimal("3.5000"),
        "output_price_per_1m": Decimal("10.5000"),
        "cached_input_price_per_1m": Decimal("0.8750"),
        "currency": "USD",
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
        "effective_until": None,
        "source": "CONFIGURED_ESTIMATE",
    },
    {
        "id": "price-gemini-1-5-flash-v1",
        "provider": "google",
        "model": "gemini-1.5-flash",
        "version": 1,
        "input_price_per_1m": Decimal("0.0750"),
        "output_price_per_1m": Decimal("0.3000"),
        "cached_input_price_per_1m": Decimal("0.01875"),
        "currency": "USD",
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
        "effective_until": None,
        "source": "CONFIGURED_ESTIMATE",
    },
    {
        "id": "price-local-llama3-v1",
        "provider": "local",
        "model": "llama-3-70b",
        "version": 1,
        "input_price_per_1m": Decimal("0.0000"),
        "output_price_per_1m": Decimal("0.0000"),
        "cached_input_price_per_1m": Decimal("0.0000"),
        "currency": "USD",
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
        "effective_until": None,
        "source": "CONFIGURED_ESTIMATE",
    },
]


class ModelPricingRegistry:
    """Encapsulates deterministic token pricing resolution and cost calculation."""

    MILLION = Decimal("1000000")
    PRECISION = Decimal("0.00000001")

    @classmethod
    def calculate_cost(
        cls,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        pricing: ModelPricing | None,
    ) -> CostCalculationResult:
        """Deterministic calculation:
        input_cost = (input_tokens / 1_000_000) * input_price
        output_cost = (output_tokens / 1_000_000) * output_price
        cached_cost = (cached_tokens / 1_000_000) * cached_price
        total_cost = input_cost + output_cost + cached_cost
        """
        if not pricing:
            return CostCalculationResult(
                total_cost=Decimal("0.0"),
                input_cost=Decimal("0.0"),
                output_cost=Decimal("0.0"),
                cached_cost=Decimal("0.0"),
                pricing_version=0,
                is_pricing_known=False,
            )

        inp_tok = Decimal(max(0, input_tokens))
        out_tok = Decimal(max(0, output_tokens))
        cac_tok = Decimal(max(0, cached_tokens))

        input_cost = (inp_tok / cls.MILLION) * Decimal(str(pricing.input_price_per_1m))
        output_cost = (out_tok / cls.MILLION) * Decimal(str(pricing.output_price_per_1m))

        cached_rate = (
            Decimal(str(pricing.cached_input_price_per_1m))
            if pricing.cached_input_price_per_1m is not None
            else Decimal(str(pricing.input_price_per_1m))
        )
        cached_cost = (cac_tok / cls.MILLION) * cached_rate

        total_cost = input_cost + output_cost + cached_cost

        return CostCalculationResult(
            total_cost=total_cost.quantize(cls.PRECISION, rounding=ROUND_HALF_UP),
            input_cost=input_cost.quantize(cls.PRECISION, rounding=ROUND_HALF_UP),
            output_cost=output_cost.quantize(cls.PRECISION, rounding=ROUND_HALF_UP),
            cached_cost=cached_cost.quantize(cls.PRECISION, rounding=ROUND_HALF_UP),
            pricing_version=pricing.version,
            is_pricing_known=True,
        )

    @classmethod
    def resolve_pricing(
        cls,
        provider: str,
        model: str,
        timestamp: datetime,
        pricing_records: list[ModelPricing],
    ) -> ModelPricing | None:
        """Find the matching version of model pricing effective at the given timestamp."""
        matching: list[ModelPricing] = []
        p_lower = provider.lower()
        m_lower = model.lower()

        for rec in pricing_records:
            if rec.provider.lower() != p_lower or rec.model.lower() != m_lower:
                continue

            # Ensure timezone awareness for comparison
            ts = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=UTC)
            eff_from = (
                rec.effective_from
                if rec.effective_from.tzinfo
                else rec.effective_from.replace(tzinfo=UTC)
            )
            eff_until = (
                rec.effective_until
                if (rec.effective_until is None or rec.effective_until.tzinfo)
                else rec.effective_until.replace(tzinfo=UTC)
            )

            if eff_from <= ts and (eff_until is None or ts < eff_until):
                matching.append(rec)

        if not matching:
            return None

        # Return latest version if multiple match
        matching.sort(key=lambda r: r.version, reverse=True)
        return matching[0]
