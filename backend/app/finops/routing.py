"""Cost-aware model routing engine with quality floors and security policy precedence."""

from decimal import Decimal
from typing import Any, NamedTuple

from app.compliance.enums import DataClassificationLevel
from app.finops.exceptions import CostPolicyViolationError
from app.finops.models import ModelPricing


class ModelCandidate(NamedTuple):
    provider: str
    model: str
    quality_score: float  # 0.0 to 1.0 (from evaluation/benchmarks)
    latency_ms: int
    pricing: ModelPricing | None
    is_external: bool = True
    capabilities: list[str] = []


# Alias for backward compatibility
CandidateModel = ModelCandidate


class RoutingDecision(NamedTuple):
    selected_provider: str
    selected_model: str
    routing_score: float
    reason: str
    evaluated_candidates: list[dict[str, object]]


class CostAwareRouter:
    """Selects the most cost-effective model that meets quality and security constraints."""

    @classmethod
    def select_model(
        cls,
        candidates: list[ModelCandidate],
        data_classification: str = DataClassificationLevel.INTERNAL.value,
        minimum_quality_threshold: float = 0.70,
        required_capability: str | None = None,
        weight_quality: float = 0.50,
        weight_cost: float = 0.35,
        weight_latency: float = 0.15,
    ) -> RoutingDecision:
        """Evaluate candidates using deterministic scoring:
        Score = (w_q * quality) - (w_c * normalized_cost) - (w_l * normalized_latency)

        CONSTRAINTS PRECEDENCE:
        1. Security / Compliance (RESTRICTED cannot route to external provider)
        2. Capability (must support required_capability if specified)
        3. Quality Floor (quality_score >= minimum_quality_threshold)
        """
        if not candidates:
            raise CostPolicyViolationError(
                "No candidate models available for routing.",
                policy_name="COST_AWARE_ROUTING",
                enforcement_mode="BLOCK",
            )

        scored_candidates: list[dict[str, Any]] = []

        # Find max cost and max latency for normalization
        max_cost = Decimal("0.0001")
        max_latency = 1

        for c in candidates:
            cost_metric = (
                Decimal(str(c.pricing.input_price_per_1m))
                + Decimal(str(c.pricing.output_price_per_1m))
                if c.pricing
                else Decimal("10.0")
            )
            if cost_metric > max_cost:
                max_cost = cost_metric
            if c.latency_ms > max_latency:
                max_latency = c.latency_ms

        for c in candidates:
            # 1. Security / Compliance constraint (TASK 39)
            if data_classification == DataClassificationLevel.RESTRICTED.value and c.is_external:
                scored_candidates.append(
                    {
                        "model": c.model,
                        "provider": c.provider,
                        "eligible": False,
                        "rejection_reason": "BLOCKED_BY_POLICY: Restricted data prohibited on external providers.",
                    }
                )
                continue

            # 2. Capability constraint
            if required_capability and required_capability not in c.capabilities:
                scored_candidates.append(
                    {
                        "model": c.model,
                        "provider": c.provider,
                        "eligible": False,
                        "rejection_reason": f"Lacks required capability '{required_capability}'.",
                    }
                )
                continue

            # 3. Quality Floor constraint
            if c.quality_score < minimum_quality_threshold:
                scored_candidates.append(
                    {
                        "model": c.model,
                        "provider": c.provider,
                        "eligible": False,
                        "rejection_reason": f"Quality score ({c.quality_score}) below required floor ({minimum_quality_threshold}).",
                    }
                )
                continue

            # Calculate normalized cost & latency [0.0 to 1.0]
            cost_val = (
                Decimal(str(c.pricing.input_price_per_1m))
                + Decimal(str(c.pricing.output_price_per_1m))
                if c.pricing
                else Decimal("10.0")
            )
            norm_cost = float(cost_val / max_cost)
            norm_latency = float(c.latency_ms / max_latency)

            # Score formula: higher is better
            # Perfect model: quality=1.0, norm_cost=0.0, norm_latency=0.0 -> score = 0.50
            score = (
                (weight_quality * c.quality_score)
                - (weight_cost * norm_cost)
                - (weight_latency * norm_latency)
            )

            scored_candidates.append(
                {
                    "model": c.model,
                    "provider": c.provider,
                    "eligible": True,
                    "score": round(score, 4),
                    "quality": c.quality_score,
                    "norm_cost": round(norm_cost, 4),
                    "norm_latency": round(norm_latency, 4),
                }
            )

        eligible = [c for c in scored_candidates if c.get("eligible")]
        if not eligible:
            raise CostPolicyViolationError(
                f"No eligible models met security, quality floor ({minimum_quality_threshold}), or capability constraints.",
                policy_name="COST_AWARE_ROUTING",
                enforcement_mode="BLOCK",
            )

        # Sort by score descending
        eligible.sort(key=lambda x: float(str(x.get("score", -999.0))), reverse=True)
        winner = eligible[0]

        return RoutingDecision(
            selected_provider=str(winner["provider"]),
            selected_model=str(winner["model"]),
            routing_score=float(str(winner["score"])),
            reason=f"Selected model '{winner['model']}' achieved highest balanced efficiency score ({winner['score']}) exceeding quality floor.",
            evaluated_candidates=scored_candidates,
        )
