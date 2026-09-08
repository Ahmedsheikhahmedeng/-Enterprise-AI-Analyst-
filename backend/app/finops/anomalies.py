"""Deterministic cost and token anomaly detection engine."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.finops.enums import AnomalyType, FinOpsSeverity
from app.finops.models import CostAnomaly, CostEvent


class AnomalyDetectionEngine:
    """Detects cost surges and abnormal token spikes against historical baseline averages."""

    @classmethod
    def detect_cost_spikes(
        cls,
        organization_id: uuid.UUID,
        baseline_cost: Decimal,
        current_cost: Decimal,
        spike_threshold_percent: float = 100.0,  # 100% = 2x baseline
        affected_entity: str | None = None,
    ) -> CostAnomaly | None:
        """Evaluate if current spend exceeds baseline by threshold."""
        if baseline_cost <= 0:
            return None

        deviation = float(((current_cost - baseline_cost) / baseline_cost) * 100)
        if deviation < spike_threshold_percent:
            return None

        # Determine severity based on deviation magnitude
        if deviation >= 300.0:  # 4x baseline
            severity = FinOpsSeverity.CRITICAL.value
        elif deviation >= 150.0:  # 2.5x baseline
            severity = FinOpsSeverity.ERROR.value
        else:
            severity = FinOpsSeverity.WARNING.value

        impact = max(Decimal("0.0"), current_cost - baseline_cost)

        return CostAnomaly(
            id=f"ano-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            anomaly_type=AnomalyType.SUDDEN_SPIKE.value,
            severity=severity,
            status="OPEN",
            baseline_amount=baseline_cost,
            actual_amount=current_cost,
            deviation_percent=round(deviation, 2),
            estimated_impact=impact,
            description=f"Spending spike detected on {affected_entity or 'organization'}: Actual spend (${current_cost}) deviated by +{deviation:.1f}% from baseline (${baseline_cost}).",
            affected_entity=affected_entity,
            detected_at=datetime.now(UTC),
        )

    @classmethod
    def detect_token_spikes(
        cls,
        organization_id: uuid.UUID,
        baseline_tokens: int,
        current_tokens: int,
        spike_threshold_percent: float = 150.0,
        affected_entity: str | None = None,
    ) -> CostAnomaly | None:
        """Evaluate if token consumption exceeds historical rolling average."""
        if baseline_tokens <= 0:
            return None

        deviation = float(((current_tokens - baseline_tokens) / baseline_tokens) * 100)
        if deviation < spike_threshold_percent:
            return None

        severity = FinOpsSeverity.WARNING.value if deviation < 300.0 else FinOpsSeverity.ERROR.value

        return CostAnomaly(
            id=f"ano-{uuid.uuid4().hex[:16]}",
            organization_id=organization_id,
            anomaly_type=AnomalyType.UNUSUAL_TOKEN_VOLUME.value,
            severity=severity,
            status="OPEN",
            baseline_amount=Decimal(str(baseline_tokens)),
            actual_amount=Decimal(str(current_tokens)),
            deviation_percent=round(deviation, 2),
            estimated_impact=Decimal("0.0"),
            description=f"Abnormal token surge on {affected_entity or 'organization'}: Incurred {current_tokens} tokens (+{deviation:.1f}% above baseline {baseline_tokens}).",
            affected_entity=affected_entity,
            detected_at=datetime.now(UTC),
        )

    @classmethod
    def calculate_rolling_baseline(cls, historical_events: list[CostEvent]) -> Decimal:
        """Compute simple moving average spend across historical event batches."""
        if not historical_events:
            return Decimal("0.0")
        total = sum((Decimal(str(e.estimated_cost)) for e in historical_events), Decimal("0.0"))
        return total / len(historical_events)
