"""Tests for FinOps gateway-to-ledger reconciliation audits and discrepancy checks."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.finops.enums import CostOperation, ReconciliationStatus
from app.finops.models import CostEvent
from app.finops.reconciliation import ReconciliationEngine


def test_reconciliation_perfect_match() -> None:
    """When all gateway requests are correctly attributed in the ledger with matching tokens."""
    now = datetime.now(UTC)
    org_id = uuid.uuid4()

    gateway_records = [
        {
            "request_id": "req-1",
            "provider": "openai",
            "model": "gpt-4o",
            "total_tokens": 1500,
            "estimated_cost": "0.0075",
            "status": "SUCCESS",
        },
        {
            "request_id": "req-2",
            "provider": "anthropic",
            "model": "claude-3-5-sonnet",
            "total_tokens": 3200,
            "estimated_cost": "0.0240",
            "status": "SUCCESS",
        },
    ]
    ledger_records = [
        CostEvent(
            id="evt-1",
            organization_id=org_id,
            request_id="req-1",
            provider="openai",
            model="gpt-4o",
            operation=CostOperation.CHAT.value,
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost=Decimal("0.0075"),
            pricing_version=1,
            timestamp=now,
        ),
        CostEvent(
            id="evt-2",
            organization_id=org_id,
            request_id="req-2",
            provider="anthropic",
            model="claude-3-5-sonnet",
            operation=CostOperation.CHAT.value,
            input_tokens=2000,
            output_tokens=1200,
            total_tokens=3200,
            estimated_cost=Decimal("0.0240"),
            pricing_version=1,
            timestamp=now,
        ),
    ]

    result = ReconciliationEngine.reconcile(
        organization_id=org_id,
        gateway_requests=gateway_records,
        cost_events=ledger_records,
        period_start=now - timedelta(hours=1),
        period_end=now,
    )
    assert result.status == ReconciliationStatus.MATCHED.value
    assert result.matched_count == 2
    assert result.missing_count == 0
    assert result.mismatched_count == 0
    assert result.discrepancy_amount == Decimal("0.0")


def test_reconciliation_detects_missing_ledger_events() -> None:
    """Detects requests that executed in LLM gateway but were dropped before ledger ingestion."""
    now = datetime.now(UTC)
    org_id = uuid.uuid4()

    gateway_records = [
        {
            "request_id": "req-1",
            "provider": "openai",
            "model": "gpt-4o",
            "total_tokens": 1000,
            "estimated_cost": "0.005",
            "status": "SUCCESS",
        },
        {
            "request_id": "req-2",
            "provider": "openai",
            "model": "gpt-4o",
            "total_tokens": 2000,
            "estimated_cost": "0.010",
            "status": "SUCCESS",
        },
    ]
    # req-2 was dropped from ledger
    ledger_records = [
        CostEvent(
            id="evt-1",
            organization_id=org_id,
            request_id="req-1",
            provider="openai",
            model="gpt-4o",
            operation=CostOperation.CHAT.value,
            total_tokens=1000,
            estimated_cost=Decimal("0.005"),
            pricing_version=1,
            timestamp=now,
        ),
    ]

    result = ReconciliationEngine.reconcile(
        organization_id=org_id,
        gateway_requests=gateway_records,
        cost_events=ledger_records,
        period_start=now - timedelta(hours=1),
        period_end=now,
    )
    assert result.status == ReconciliationStatus.MISMATCHED.value or result.missing_count > 0
    assert result.matched_count == 1
    assert result.missing_count == 1


def test_reconciliation_detects_token_mismatch() -> None:
    """Flags discrepancy if token count recorded in ledger differs from gateway."""
    now = datetime.now(UTC)
    org_id = uuid.uuid4()

    gateway_records = [
        {
            "request_id": "req-1",
            "provider": "openai",
            "model": "gpt-4o",
            "total_tokens": 5000,
            "estimated_cost": "0.025",
            "status": "SUCCESS",
        },
    ]
    ledger_records = [
        CostEvent(
            id="evt-1",
            organization_id=org_id,
            request_id="req-1",
            provider="openai",
            model="gpt-4o",
            operation=CostOperation.CHAT.value,
            total_tokens=3000,  # mismatch!
            estimated_cost=Decimal("0.015"),
            pricing_version=1,
            timestamp=now,
        ),
    ]

    result = ReconciliationEngine.reconcile(
        organization_id=org_id,
        gateway_requests=gateway_records,
        cost_events=ledger_records,
        period_start=now - timedelta(hours=1),
        period_end=now,
    )
    assert result.mismatched_count == 1
