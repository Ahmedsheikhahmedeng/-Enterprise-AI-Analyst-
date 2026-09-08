"""Evidence-based FinOps recommendations and caching ROI analysis."""

import uuid
from decimal import Decimal

from app.finops.enums import RecommendationType
from app.finops.models import CostEvent, OptimizationRecommendation


class OptimizationEngine:
    """Generates actionable cost optimization recommendations backed by concrete telemetry evidence."""

    @classmethod
    def evaluate_model_downgrade_opportunity(
        cls,
        organization_id: uuid.UUID,
        events: list[CostEvent],
        expensive_model: str = "gpt-4o",
        cheaper_alternative: str = "gpt-4o-mini",
        expected_discount_ratio: Decimal = Decimal("0.85"),  # ~85% cheaper
    ) -> OptimizationRecommendation | None:
        """Analyze if high volume of simple operations on expensive models could be migrated."""
        matching_events = [e for e in events if e.model.lower() == expensive_model.lower()]
        if not matching_events:
            return None

        current_spend = sum(
            (Decimal(str(e.estimated_cost)) for e in matching_events), Decimal("0.0")
        )
        if current_spend < Decimal("5.0"):  # Low financial materiality threshold
            return None

        expected_savings = current_spend * expected_discount_ratio

        return OptimizationRecommendation(
            id=f"rec-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            recommendation_type=RecommendationType.SWITCH_TO_LOWER_COST_MODEL.value,
            status="OPEN",
            title=f"Migrate routine workloads from '{expensive_model}' to '{cheaper_alternative}'",
            description=(
                f"Detected {len(matching_events)} invocations on '{expensive_model}' totaling ${current_spend:.2f}. "
                f"Switching eligible standard queries to '{cheaper_alternative}' can reduce model costs by ~{int(expected_discount_ratio * 100)}% "
                f"with negligible quality degradation on structured and summarization tasks."
            ),
            current_cost=current_spend,
            expected_saving=expected_savings,
            quality_impact="NEGLIGIBLE",
            latency_impact="FASTER",
            confidence=0.88,
            evidence={
                "event_count": len(matching_events),
                "target_model": cheaper_alternative,
                "calculated_saving": str(expected_savings),
            },
        )

    @classmethod
    def evaluate_caching_roi(
        cls,
        organization_id: uuid.UUID,
        events: list[CostEvent],
    ) -> dict[str, object]:
        """Compute caching ROI: cache hit rate, tokens saved, and cost saved."""
        total_requests = len(events)
        if total_requests == 0:
            return {"hit_rate": 0.0, "tokens_saved": 0, "cost_saved": Decimal("0.0")}

        cache_hits = sum(1 for e in events if e.cached_tokens > 0)
        total_cached_tokens = sum(e.cached_tokens for e in events)

        # Estimate savings as difference between standard input price and cached discount rate
        cost_saved = Decimal("0.0")
        for e in events:
            if e.cached_tokens > 0:
                # Approximate 50% discount on cached tokens
                cost_saved += (Decimal(str(e.cached_tokens)) / Decimal("1000000")) * Decimal("1.25")

        hit_rate = round((cache_hits / total_requests) * 100.0, 2)

        return {
            "total_requests": total_requests,
            "cache_hits": cache_hits,
            "hit_rate_percent": hit_rate,
            "tokens_saved": total_cached_tokens,
            "cost_saved": cost_saved,
        }

    @classmethod
    def evaluate_context_reduction(
        cls,
        organization_id: uuid.UUID,
        events: list[CostEvent],
    ) -> OptimizationRecommendation | None:
        """Detect disproportionate prompt context size (>85% input tokens)."""
        high_context_events = [
            e
            for e in events
            if e.total_tokens > 2000 and (e.input_tokens / max(1, e.total_tokens)) > 0.85
        ]

        if len(high_context_events) < 5:
            return None

        spend = sum((Decimal(str(e.estimated_cost)) for e in high_context_events), Decimal("0.0"))
        expected_savings = spend * Decimal("0.30")  # ~30% savings with chunk compression

        return OptimizationRecommendation(
            id=f"rec-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            recommendation_type=RecommendationType.REDUCE_CONTEXT.value,
            status="OPEN",
            title="Enable Prompt Compression & RAG Chunk Pruning",
            description=(
                f"Identified {len(high_context_events)} requests where prompt input constitutes >85% of total tokens. "
                "Applying relevance filtering and semantic chunk pruning can eliminate redundant token transmission."
            ),
            current_cost=spend,
            expected_saving=expected_savings,
            quality_impact="NEGLIGIBLE",
            latency_impact="FASTER",
            confidence=0.82,
            evidence={
                "high_context_count": len(high_context_events),
                "potential_saving_percent": 30.0,
            },
        )
