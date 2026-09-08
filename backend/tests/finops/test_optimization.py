"""Tests for FinOps evidence-backed AI optimization and recommendation engine."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.finops.enums import RecommendationType
from app.finops.models import CostEvent
from app.finops.optimization import OptimizationEngine


def test_model_downgrade_recommendation() -> None:
    """Recommends lower cost model when expensive model spend is high."""
    org_id = uuid.uuid4()
    now = datetime.now(UTC)
    events = [
        CostEvent(id=f"e-{i}", model="gpt-4o", estimated_cost=Decimal("1.50"), timestamp=now)
        for i in range(10)  # Total $15.00 > $5.0 threshold
    ]
    rec = OptimizationEngine.evaluate_model_downgrade_opportunity(
        organization_id=org_id,
        events=events,
        expensive_model="gpt-4o",
        cheaper_alternative="gpt-4o-mini",
        expected_discount_ratio=Decimal("0.85"),
    )
    assert rec is not None
    assert rec.recommendation_type == RecommendationType.SWITCH_TO_LOWER_COST_MODEL.value
    assert rec.expected_saving == Decimal("15.00") * Decimal("0.85")
    assert rec.quality_impact == "NEGLIGIBLE"


def test_caching_roi_analysis() -> None:
    """Calculates ROI, hit rate, and tokens saved from caching telemetries."""
    org_id = uuid.uuid4()
    now = datetime.now(UTC)
    events = [
        CostEvent(
            id="e1",
            total_tokens=1000,
            cached_tokens=500,
            estimated_cost=Decimal("0.01"),
            timestamp=now,
        ),
        CostEvent(
            id="e2",
            total_tokens=1000,
            cached_tokens=0,
            estimated_cost=Decimal("0.02"),
            timestamp=now,
        ),
    ]
    roi = OptimizationEngine.evaluate_caching_roi(organization_id=org_id, events=events)
    assert roi["total_requests"] == 2
    assert roi["cache_hits"] == 1
    assert roi["hit_rate_percent"] == 50.0
    assert roi["tokens_saved"] == 500


def test_context_reduction_recommendation() -> None:
    """Recommends prompt compression when input tokens exceed 85% of total."""
    org_id = uuid.uuid4()
    now = datetime.now(UTC)
    events = [
        CostEvent(
            id=f"e-{i}",
            total_tokens=5000,
            input_tokens=4800,  # 96% input tokens
            output_tokens=200,
            estimated_cost=Decimal("0.05"),
            timestamp=now,
        )
        for i in range(6)
    ]
    rec = OptimizationEngine.evaluate_context_reduction(organization_id=org_id, events=events)
    assert rec is not None
    assert rec.recommendation_type == RecommendationType.REDUCE_CONTEXT.value
