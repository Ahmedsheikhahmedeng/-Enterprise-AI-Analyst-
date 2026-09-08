"""Budget validation and pre-flight token/cost estimation service."""

from decimal import Decimal

from app.llm_gateway.domain.errors import (
    CostBudgetExceededError,
    TokenBudgetExceededError,
)
from app.llm_gateway.domain.models import (
    LLMRequestPayload,
    ModelDefinition,
    TenantLLMPolicy,
)


class BudgetService:
    """Calculates and enforces token and cost budgets prior to execution."""

    def estimate_input_tokens(self, payload: LLMRequestPayload) -> int:
        """Heuristic token estimation: ~1.3 tokens per word across prompt messages."""
        word_count = sum(len(m.content.split()) for m in payload.messages)
        # Add metadata or instruction weight
        return max(1, int(word_count * 1.35) + 20)

    def estimate_cost(
        self,
        input_tokens: int,
        max_output_tokens: int,
        model: ModelDefinition,
    ) -> Decimal:
        """Pre-flight cost estimation based on model pricing per 1,000 tokens."""
        return model.pricing.calculate_cost(input_tokens, max_output_tokens)

    def validate_budget(
        self,
        payload: LLMRequestPayload,
        model: ModelDefinition,
        policy: TenantLLMPolicy | None = None,
        agent_budget_remaining: int | None = None,
    ) -> tuple[int, Decimal]:
        """Verify request conforms to model context, tenant token/cost limits, and agent limits."""
        est_input_tokens = self.estimate_input_tokens(payload)
        req_output_tokens = min(payload.max_tokens, model.max_output_tokens)
        est_total_tokens = est_input_tokens + req_output_tokens

        # 1. Model context window check
        if est_total_tokens > model.context_window:
            raise TokenBudgetExceededError(
                f"Estimated tokens ({est_total_tokens}) exceed model context window ({model.context_window})."
            )

        # 2. Agent remaining budget integration (Section 11)
        if agent_budget_remaining is not None and est_total_tokens > agent_budget_remaining:
            raise TokenBudgetExceededError(
                f"Request requiring {est_total_tokens} tokens exceeds remaining agent budget ({agent_budget_remaining})."
            )

        # 3. Tenant token cap check
        if (
            policy
            and policy.max_tokens_per_request
            and est_total_tokens > policy.max_tokens_per_request
        ):
            raise TokenBudgetExceededError(
                f"Estimated tokens ({est_total_tokens}) exceed tenant limit ({policy.max_tokens_per_request})."
            )

        # 4. Pre-flight cost calculation and tenant cost cap check
        est_cost = self.estimate_cost(est_input_tokens, req_output_tokens, model)
        if policy and policy.max_cost_per_request and est_cost > policy.max_cost_per_request:
            raise CostBudgetExceededError(
                f"Estimated cost (${est_cost}) exceeds tenant cost cap (${policy.max_cost_per_request})."
            )

        return est_input_tokens, est_cost
