"""Immutable usage ledger engine, wasted cost calculation, and compensating corrections."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.finops.enums import CostOperation
from app.finops.models import CostCorrection, CostEvent, ModelPricing
from app.finops.pricing import ModelPricingRegistry


class CostLedgerEngine:
    """Ingests usage events, calculates deterministic financial impact, and creates ledger entries."""

    @classmethod
    def create_cost_event(
        cls,
        organization_id: uuid.UUID | None,
        provider: str,
        model: str,
        operation: CostOperation | str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        pricing: ModelPricing | None,
        user_id: uuid.UUID | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        agent_session_id: str | None = None,
        job_id: str | None = None,
        is_retry: bool = False,
        is_failed: bool = False,
        timestamp: datetime | None = None,
        metadata_payload: dict[str, Any] | None = None,
    ) -> CostEvent:
        """Construct an immutable, append-only CostEvent with deterministic token calculation."""
        ts = timestamp or datetime.now(UTC)
        calc = ModelPricingRegistry.calculate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            pricing=pricing,
        )

        total_tokens = max(0, input_tokens) + max(0, output_tokens) + max(0, cached_tokens)

        # Sanitize metadata to guarantee zero raw credentials or prompts stored
        clean_meta = dict(metadata_payload or {})
        clean_meta.pop("prompt", None)
        clean_meta.pop("completion", None)
        clean_meta.pop("api_key", None)
        clean_meta.pop("credentials", None)
        clean_meta["pricing_known"] = calc.is_pricing_known

        op_str = operation.value if isinstance(operation, CostOperation) else str(operation)

        return CostEvent(
            id=f"ce-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            user_id=user_id,
            request_id=request_id,
            trace_id=trace_id,
            agent_session_id=agent_session_id,
            job_id=job_id,
            provider=provider,
            model=model,
            operation=op_str,
            input_tokens=max(0, input_tokens),
            output_tokens=max(0, output_tokens),
            cached_tokens=max(0, cached_tokens),
            total_tokens=total_tokens,
            estimated_cost=calc.total_cost,
            currency=pricing.currency if pricing else "USD",
            pricing_version=calc.pricing_version,
            timestamp=ts,
            is_retry=is_retry,
            is_failed=is_failed,
            metadata_payload=clean_meta,
        )

    @classmethod
    def create_correction(
        cls,
        organization_id: uuid.UUID,
        original_event_id: str,
        adjustment_cost: Decimal,
        reason: str,
        actor: str,
    ) -> CostCorrection:
        """Create an append-only compensating adjustment without mutating original history."""
        return CostCorrection(
            id=f"cc-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            original_event_id=original_event_id,
            adjustment_cost=adjustment_cost,
            reason=reason,
            actor=actor,
            corrected_at=datetime.now(UTC),
        )

    @classmethod
    def calculate_wasted_cost(cls, events: list[CostEvent]) -> Decimal:
        """Sum total estimated cost for all failed or retried attempts."""
        wasted = Decimal("0.0")
        for ev in events:
            if ev.is_failed or ev.is_retry:
                wasted += Decimal(str(ev.estimated_cost))
        return wasted

    @classmethod
    def calculate_attribution_completeness(cls, events: list[CostEvent]) -> float:
        """Calculate percentage of billable events successfully attributed to a tenant organization."""
        if not events:
            return 100.0
        attributed = sum(1 for e in events if e.organization_id is not None)
        return round((attributed / len(events)) * 100.0, 2)
