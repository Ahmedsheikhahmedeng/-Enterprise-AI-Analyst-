"""Tests for Cost-Aware Model Routing, Quality Floor, and Compliance Constraints."""

from decimal import Decimal

import pytest

from app.finops.exceptions import CostPolicyViolationError
from app.finops.models import ModelPricing
from app.finops.routing import CostAwareRouter, ModelCandidate


def test_quality_floor_rejection() -> None:
    """A cheaper model must not be selected if its quality is below the required minimum floor."""
    cheap_pricing = ModelPricing(
        id="p-1",
        provider="cheap-ai",
        model="tiny-llm",
        input_price_per_1m=Decimal("0.10"),
        output_price_per_1m=Decimal("0.20"),
    )
    smart_pricing = ModelPricing(
        id="p-2",
        provider="premium-ai",
        model="smart-llm",
        input_price_per_1m=Decimal("5.00"),
        output_price_per_1m=Decimal("15.00"),
    )

    candidates = [
        # Candidate 1: Cheap model but fails quality floor (0.60 < 0.85)
        ModelCandidate(
            provider="cheap-ai",
            model="tiny-llm",
            quality_score=0.60,
            latency_ms=200,
            pricing=cheap_pricing,
            capabilities=["chat", "summarization"],
        ),
        # Candidate 2: Higher cost but satisfies quality floor (0.92 >= 0.85)
        ModelCandidate(
            provider="premium-ai",
            model="smart-llm",
            quality_score=0.92,
            latency_ms=450,
            pricing=smart_pricing,
            capabilities=["chat", "summarization"],
        ),
    ]

    # Required quality floor = 0.85
    result = CostAwareRouter.select_model(
        candidates=candidates,
        minimum_quality_threshold=0.85,
        required_capability="chat",
    )
    assert result.selected_model == "smart-llm"
    assert result.selected_provider == "premium-ai"


def test_security_compliance_precedence_over_cost() -> None:
    """Classified / Restricted data blocks external cheap models regardless of cost savings."""
    cheap_pricing = ModelPricing(
        id="p-1",
        provider="public-cloud",
        model="cheap-cloud-llm",
        input_price_per_1m=Decimal("0.20"),
        output_price_per_1m=Decimal("0.50"),
    )
    secure_pricing = ModelPricing(
        id="p-2",
        provider="sovereign-cloud",
        model="secure-enterprise-llm",
        input_price_per_1m=Decimal("4.00"),
        output_price_per_1m=Decimal("12.00"),
    )

    candidates = [
        # Cheap external model not approved for restricted data
        ModelCandidate(
            provider="public-cloud",
            model="cheap-cloud-llm",
            quality_score=0.90,
            latency_ms=150,
            pricing=cheap_pricing,
            is_external=True,
            capabilities=["chat"],
        ),
        # Compliant sovereign / internal model (more expensive)
        ModelCandidate(
            provider="sovereign-cloud",
            model="secure-enterprise-llm",
            quality_score=0.88,
            latency_ms=250,
            pricing=secure_pricing,
            is_external=False,
            capabilities=["chat"],
        ),
    ]

    # With restricted data classification:
    result = CostAwareRouter.select_model(
        candidates=candidates,
        data_classification="RESTRICTED",
        minimum_quality_threshold=0.75,
        required_capability="chat",
    )
    assert result.selected_model == "secure-enterprise-llm"
    assert result.selected_provider == "sovereign-cloud"


def test_missing_capabilities_filtering() -> None:
    """Candidates lacking required capabilities are filtered out before scoring."""
    p = ModelPricing(
        id="p-1",
        provider="p1",
        model="m1",
        input_price_per_1m=Decimal("1.0"),
        output_price_per_1m=Decimal("2.0"),
    )
    candidates = [
        ModelCandidate(
            provider="p1",
            model="m1",
            quality_score=0.95,
            latency_ms=100,
            pricing=p,
            capabilities=["chat"],
        ),
        ModelCandidate(
            provider="p2",
            model="m2",
            quality_score=0.90,
            latency_ms=120,
            pricing=p,
            capabilities=["chat", "function_calling"],
        ),
    ]
    result = CostAwareRouter.select_model(
        candidates=candidates,
        minimum_quality_threshold=0.80,
        required_capability="function_calling",
    )
    assert result.selected_model == "m2"


def test_empty_candidates_raises_violation() -> None:
    """When no candidates are provided, router raises CostPolicyViolationError."""
    with pytest.raises(CostPolicyViolationError):
        CostAwareRouter.select_model(
            candidates=[],
            minimum_quality_threshold=0.80,
        )
