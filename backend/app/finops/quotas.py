"""Multi-dimensional consumption quotas and rate-limiting enforcement."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.finops.enums import QuotaEnforcementMode, QuotaType
from app.finops.exceptions import QuotaExceededError
from app.finops.models import CostEvent, Quota


class QuotaEngine:
    """Evaluates request, token, and cost consumption against configured quotas."""

    @classmethod
    def evaluate_quota(
        cls,
        quota: Quota,
        events: list[CostEvent],
        as_of: datetime | None = None,
    ) -> tuple[Decimal, bool]:
        """Calculate consumption within the rolling quota window:
        window = [as_of - period_seconds, as_of]
        """
        now = as_of or datetime.now(UTC)
        window_start = now - timedelta(seconds=quota.period_seconds)

        current_usage = Decimal("0.0")

        for ev in events:
            ev_ts = ev.timestamp if ev.timestamp.tzinfo else ev.timestamp.replace(tzinfo=UTC)
            if ev_ts < window_start or ev_ts > now:
                continue

            if quota.quota_type == QuotaType.REQUESTS.value:
                current_usage += Decimal("1.0")
            elif quota.quota_type == QuotaType.TOKENS.value:
                current_usage += Decimal(str(ev.total_tokens))
            elif quota.quota_type == QuotaType.COST.value:
                current_usage += Decimal(str(ev.estimated_cost))

        is_exceeded = current_usage >= Decimal(str(quota.limit_value))
        return current_usage, is_exceeded

    @classmethod
    def enforce_quota(
        cls,
        quota: Quota,
        current_usage: Decimal,
        increment: Decimal = Decimal("1.0"),
    ) -> None:
        """Check if increment exceeds quota limit and apply configured enforcement mode."""
        if not quota.enabled:
            return

        limit = Decimal(str(quota.limit_value))
        projected = current_usage + increment

        if projected > limit:
            mode = quota.enforcement_mode
            if mode == QuotaEnforcementMode.BLOCK.value:
                raise QuotaExceededError(
                    message=f"Quota exceeded: {quota.quota_type} limit ({limit}) breached with projected consumption ({projected}).",
                    quota_type=quota.quota_type,
                    limit_value=str(limit),
                    current_usage=str(current_usage),
                )
            elif mode == QuotaEnforcementMode.WARN.value:
                # Permitted with warning log
                pass
            elif mode == QuotaEnforcementMode.ALLOW.value:
                pass
