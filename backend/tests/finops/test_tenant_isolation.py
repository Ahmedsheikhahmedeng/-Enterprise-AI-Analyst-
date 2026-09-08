"""Tests for strict multi-tenant isolation in FinOps cost ledger, budgets, quotas, and anomalies."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.finops.enums import BudgetPeriod, BudgetScope, CostOperation
from app.finops.models import Budget, CostEvent
from app.finops.repository import FinOpsRepository
from app.models.organization import Organization


@pytest.mark.asyncio
async def test_tenant_cost_event_isolation(
    db_session: AsyncSession, test_org_id: uuid.UUID, other_org_id: uuid.UUID
) -> None:
    """Verify Tenant A cannot retrieve or aggregate usage events belonging to Tenant B."""
    repo = FinOpsRepository(db_session)
    now = datetime.now(UTC)

    # Ensure organizations exist
    org_a = Organization(
        id=test_org_id,
        name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:6]}",
        created_at=now,
        updated_at=now,
    )
    org_b = Organization(
        id=other_org_id,
        name="Tenant B",
        slug=f"tenant-b-{uuid.uuid4().hex[:6]}",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    # Event for Tenant A
    event_a = CostEvent(
        id=f"evt-{uuid.uuid4()}",
        organization_id=test_org_id,
        provider="openai",
        model="gpt-4o",
        operation=CostOperation.CHAT.value,
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        estimated_cost=Decimal("0.01"),
        currency="USD",
        pricing_version=1,
        timestamp=now,
        created_at=now,
        updated_at=now,
    )
    # Event for Tenant B
    event_b = CostEvent(
        id=f"evt-{uuid.uuid4()}",
        organization_id=other_org_id,
        provider="anthropic",
        model="claude-3-5-sonnet",
        operation=CostOperation.RAG.value,
        input_tokens=2000,
        output_tokens=1000,
        total_tokens=3000,
        estimated_cost=Decimal("0.03"),
        currency="USD",
        pricing_version=1,
        timestamp=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([event_a, event_b])
    await db_session.flush()

    # Query usage for Tenant A
    usage_a = await repo.list_events(
        organization_id=test_org_id,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1),
    )
    assert len(usage_a) == 1
    assert usage_a[0].organization_id == test_org_id
    assert usage_a[0].provider == "openai"

    # Query usage for Tenant B
    usage_b = await repo.list_events(
        organization_id=other_org_id,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1),
    )
    assert len(usage_b) == 1
    assert usage_b[0].organization_id == other_org_id
    assert usage_b[0].provider == "anthropic"


@pytest.mark.asyncio
async def test_tenant_budget_isolation(
    db_session: AsyncSession, test_org_id: uuid.UUID, other_org_id: uuid.UUID
) -> None:
    """Verify budgets are isolated per organization."""
    repo = FinOpsRepository(db_session)
    now = datetime.now(UTC)

    # Ensure organizations exist
    org_a = Organization(
        id=test_org_id,
        name="Tenant A",
        slug=f"tenant-a-{uuid.uuid4().hex[:6]}",
        created_at=now,
        updated_at=now,
    )
    org_b = Organization(
        id=other_org_id,
        name="Tenant B",
        slug=f"tenant-b-{uuid.uuid4().hex[:6]}",
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([org_a, org_b])
    await db_session.flush()

    b_a = Budget(
        id=f"bg-{uuid.uuid4()}",
        organization_id=test_org_id,
        scope=BudgetScope.ORGANIZATION.value,
        period=BudgetPeriod.MONTHLY.value,
        limit_amount=Decimal("500.0"),
        starts_at=now,
        created_at=now,
        updated_at=now,
    )
    b_b = Budget(
        id=f"bg-{uuid.uuid4()}",
        organization_id=other_org_id,
        scope=BudgetScope.ORGANIZATION.value,
        period=BudgetPeriod.MONTHLY.value,
        limit_amount=Decimal("1500.0"),
        starts_at=now,
        created_at=now,
        updated_at=now,
    )
    db_session.add_all([b_a, b_b])
    await db_session.flush()

    budgets_a = await repo.list_budgets(organization_id=test_org_id)
    assert len(budgets_a) == 1
    assert budgets_a[0].limit_amount == Decimal("500.0")

    budgets_b = await repo.list_budgets(organization_id=other_org_id)
    assert len(budgets_b) == 1
    assert budgets_b[0].limit_amount == Decimal("1500.0")
