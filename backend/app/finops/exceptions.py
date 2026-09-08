"""Domain exceptions for Enterprise FinOps, AI Cost Governance & Usage Optimization."""

from typing import Any


class FinOpsError(Exception):
    """Base exception for all FinOps and Cost Governance errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class BudgetExhaustedError(FinOpsError):
    """Raised when an operation would exceed or has exceeded the active budget limit."""

    def __init__(
        self,
        message: str,
        budget_id: str | None = None,
        limit_amount: str | None = None,
        current_spent: str | None = None,
    ) -> None:
        super().__init__(
            message,
            {
                "budget_id": budget_id,
                "limit_amount": limit_amount,
                "current_spent": current_spent,
            },
        )


class QuotaExceededError(FinOpsError):
    """Raised when request rate, token consumption, or spend exceeds an enforced quota."""

    def __init__(
        self,
        message: str,
        quota_type: str | None = None,
        limit_value: str | None = None,
        current_usage: str | None = None,
    ) -> None:
        super().__init__(
            message,
            {
                "quota_type": quota_type,
                "limit_value": limit_value,
                "current_usage": current_usage,
            },
        )


class CostPolicyViolationError(FinOpsError):
    """Raised when an operation violates per-request or daily cost/token constraints."""

    def __init__(
        self,
        message: str,
        policy_name: str | None = None,
        enforcement_mode: str | None = None,
    ) -> None:
        super().__init__(
            message,
            {
                "policy_name": policy_name,
                "enforcement_mode": enforcement_mode,
            },
        )


class PricingNotFoundError(FinOpsError):
    """Raised when strict cost estimation requires registered pricing rates that are missing."""

    def __init__(self, provider: str, model: str) -> None:
        message = f"No active pricing rate registered for provider='{provider}', model='{model}'."
        super().__init__(message, {"provider": provider, "model": model})
