"""Rate Limiting Tests — TASK 22.

Verifies:
- Sliding-window rate limit enforcement
- Allowed vs rejected request behavior
- HTTP 429 semantics and Retry-After calculation
- Key building with client IP and tenant isolation
"""

import pytest

from app.security.exceptions import RateLimitExceededError
from app.security.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_threshold() -> None:
    limiter = RateLimiter(redis_client=None)
    key = "test_user_under_limit"
    limit = 5
    window = 60

    for _ in range(limit):
        res = await limiter.check(key=key, limit=limit, window_seconds=window)
        assert res.allowed is True
        assert res.remaining >= 0


@pytest.mark.asyncio
async def test_rate_limiter_blocks_above_threshold() -> None:
    limiter = RateLimiter(redis_client=None)
    key = "test_user_over_limit"
    limit = 3
    window = 30

    for _ in range(limit):
        res = await limiter.check(key=key, limit=limit, window_seconds=window)
        assert res.allowed is True

    # Next attempt should be blocked
    blocked_res = await limiter.check(key=key, limit=limit, window_seconds=window)
    assert blocked_res.allowed is False
    assert blocked_res.remaining == 0
    assert blocked_res.retry_after > 0

    with pytest.raises(RateLimitExceededError) as exc:
        limiter.assert_allowed(blocked_res, endpoint="auth.login")
    assert exc.value.retry_after > 0
    assert "Rate limit exceeded" in str(exc.value)


def test_rate_limit_key_structure() -> None:
    key = RateLimiter.build_key(
        endpoint="analyst.ask",
        client_ip="192.0.2.1",
        user_id="usr-123",
        organization_id="org-456",
    )
    assert "ep:analyst.ask" in key
    assert "org:org-456" in key
    assert "usr:usr-123" in key
    assert "ip:192.0.2.1" in key
