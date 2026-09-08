"""Tests for FinOps deterministic cost and token anomaly detection."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.finops.anomalies import AnomalyDetectionEngine
from app.finops.enums import AnomalyType, FinOpsSeverity
from app.finops.models import CostEvent


def test_no_anomaly_when_within_normal_baseline() -> None:
    """Spend close to baseline does not trigger anomaly."""
    org_id = uuid.uuid4()
    anomaly = AnomalyDetectionEngine.detect_cost_spikes(
        organization_id=org_id,
        baseline_cost=Decimal("10.0"),
        current_cost=Decimal("11.5"),
        spike_threshold_percent=100.0,
    )
    assert anomaly is None


def test_sudden_spike_anomaly_detected() -> None:
    """A sudden 2.5x spend over baseline triggers a cost anomaly."""
    org_id = uuid.uuid4()
    anomaly = AnomalyDetectionEngine.detect_cost_spikes(
        organization_id=org_id,
        baseline_cost=Decimal("10.0"),
        current_cost=Decimal("25.0"),  # 150% deviation
        spike_threshold_percent=100.0,
        affected_entity="tenant-alpha",
    )
    assert anomaly is not None
    assert anomaly.anomaly_type == AnomalyType.SUDDEN_SPIKE.value
    assert anomaly.severity == FinOpsSeverity.ERROR.value
    assert anomaly.deviation_percent == 150.0
    assert anomaly.estimated_impact == Decimal("15.0")


def test_token_spike_anomaly_detected() -> None:
    """Token volume surge exceeding threshold triggers token anomaly."""
    org_id = uuid.uuid4()
    anomaly = AnomalyDetectionEngine.detect_token_spikes(
        organization_id=org_id,
        baseline_tokens=100_000,
        current_tokens=300_000,  # 200% deviation > 150%
        spike_threshold_percent=150.0,
        affected_entity="rag-pipeline",
    )
    assert anomaly is not None
    assert anomaly.anomaly_type == AnomalyType.UNUSUAL_TOKEN_VOLUME.value
    assert anomaly.deviation_percent == 200.0


def test_rolling_baseline_calculation() -> None:
    """Computes moving average spend across event history."""
    now = datetime.now(UTC)
    events = [
        CostEvent(
            id="e1",
            provider="p",
            model="m",
            operation="CHAT",
            estimated_cost=Decimal("10.0"),
            timestamp=now,
        ),
        CostEvent(
            id="e2",
            provider="p",
            model="m",
            operation="CHAT",
            estimated_cost=Decimal("20.0"),
            timestamp=now,
        ),
    ]
    baseline = AnomalyDetectionEngine.calculate_rolling_baseline(events)
    assert baseline == Decimal("15.0")
