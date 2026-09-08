"""Replay & Idempotency Protection Tests — TASK 22.

Verifies:
- First-time Idempotency-Key acquisition
- Duplicate key replay detection with matching payload
- Tampering / payload mismatch rejection (ReplayViolationError)
- Request parameter fingerprinting
"""

import pytest

from app.security.exceptions import ReplayViolationError
from app.security.replay import IdempotencyManager


def test_fingerprint_deterministic() -> None:
    fp1 = IdempotencyManager.compute_fingerprint(
        method="POST",
        path="/api/v1/reports",
        body='{"title": "Q3 Report", "table_id": "1"}',
    )
    fp2 = IdempotencyManager.compute_fingerprint(
        method="POST",
        path="/api/v1/reports",
        body='{"title": "Q3 Report", "table_id": "1"}',
    )
    assert fp1 == fp2

    fp_diff = IdempotencyManager.compute_fingerprint(
        method="POST",
        path="/api/v1/reports",
        body='{"title": "Q4 Report", "table_id": "2"}',
    )
    assert fp1 != fp_diff


@pytest.mark.asyncio
async def test_idempotency_workflow() -> None:
    mgr = IdempotencyManager(redis_client=None, default_ttl_seconds=60)
    key = "client-tx-uuid-12345"
    fp = IdempotencyManager.compute_fingerprint("POST", "/api/v1/reports", b"data")

    # 1. First request acquires lock
    is_new, record = await mgr.acquire_or_check(
        idempotency_key=key,
        fingerprint=fp,
        endpoint="/api/v1/reports",
        user_id="u-1",
        tenant_id="t-1",
    )
    assert is_new is True
    assert record.status == "IN_PROGRESS"

    # Mark completion
    await mgr.record_completion(
        idempotency_key=key, tenant_id="t-1", response_data={"report_id": "rep-99"}
    )

    # 2. Replay with identical payload returns existing record
    is_new2, record2 = await mgr.acquire_or_check(
        idempotency_key=key,
        fingerprint=fp,
        endpoint="/api/v1/reports",
        user_id="u-1",
        tenant_id="t-1",
    )
    assert is_new2 is False
    assert record2.status == "COMPLETED"
    assert record2.response_data == {"report_id": "rep-99"}

    # 3. Replay with tampered / different payload raises ReplayViolationError
    tampered_fp = IdempotencyManager.compute_fingerprint(
        "POST", "/api/v1/reports", b"DIFFERENT_BODY"
    )
    with pytest.raises(ReplayViolationError) as exc:
        await mgr.acquire_or_check(
            idempotency_key=key,
            fingerprint=tampered_fp,
            endpoint="/api/v1/reports",
            user_id="u-1",
            tenant_id="t-1",
        )
    assert "different request payload" in str(exc.value)
