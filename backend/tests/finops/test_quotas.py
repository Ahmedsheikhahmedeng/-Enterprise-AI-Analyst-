"""Tests for FinOps multi-dimensional quotas and deterministic enforcement."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.finops.enums import QuotaEnforcementMode, QuotaType
from app.finops.exceptions import QuotaExceededError
from app.finops.models import CostEvent, Quota
from app.finops.quotas import QuotaEngine


def test_quota_enforcement_within_limit() -> None:
    """Operations below quota threshold do not raise errors."""
    now = datetime.now(UTC)
    quota = Quota(
        id="q-1",
        organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        quota_type=QuotaType.TOKENS.value,
        limit_value=Decimal("100000"),
        period_seconds=86400,
        enforcement_mode=QuotaEnforcementMode.BLOCK.value,
        enabled=True,
    )
    events = [
        CostEvent(id="e1", total_tokens=80000, timestamp=now),
    ]
    usage, is_exceeded = QuotaEngine.evaluate_quota(quota=quota, events=events, as_of=now)
    assert usage == Decimal("80000")
    assert is_exceeded is False

    # Enforce with small increment -> no error
    QuotaEngine.enforce_quota(quota=quota, current_usage=usage, increment=Decimal("10000"))


def test_quota_enforcement_block_mode() -> None:
    """When quota limit is breached in BLOCK mode, QuotaExceededError is raised."""
    quota = Quota(
        id="q-2",
        organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        quota_type=QuotaType.REQUESTS.value,
        limit_value=Decimal("500"),
        period_seconds=3600,
        enforcement_mode=QuotaEnforcementMode.BLOCK.value,
        enabled=True,
    )
    with pytest.raises(QuotaExceededError) as exc_info:
        QuotaEngine.enforce_quota(
            quota=quota,
            current_usage=Decimal("495"),
            increment=Decimal("10"),  # 495 + 10 = 505 > 500
        )
    assert "exceeded" in str(exc_info.value)


def test_quota_disabled_always_allows() -> None:
    """Disabled quotas never raise exceptions."""
    quota = Quota(
        id="q-4",
        organization_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        quota_type=QuotaType.REQUESTS.value,
        limit_value=Decimal("10"),
        period_seconds=3600,
        enforcement_mode=QuotaEnforcementMode.BLOCK.value,
        enabled=False,
    )
    # Should not raise even though 100 + 5 > 10
    QuotaEngine.enforce_quota(quota=quota, current_usage=Decimal("100"), increment=Decimal("5"))
