"""Multi-dimensional budget manager tracking and enforcing resource constraints."""

import time
from dataclasses import dataclass, field

from app.agents.exceptions import BudgetExceededError


@dataclass
class TokenBudget:
    """Tracks token consumption across input, output, and total finite caps."""

    max_input_tokens: int = 40000
    max_output_tokens: int = 10000
    max_total_tokens: int = 50000

    consumed_input_tokens: int = 0
    consumed_output_tokens: int = 0
    consumed_total_tokens: int = 0

    def __init__(
        self,
        max_tokens: int = 50000,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
        max_total_tokens: int | None = None,
    ) -> None:
        self.max_total_tokens = max_total_tokens or max_tokens
        self.max_input_tokens = max_input_tokens or int(self.max_total_tokens * 0.8)
        self.max_output_tokens = max_output_tokens or int(self.max_total_tokens * 0.2)
        self.consumed_input_tokens = 0
        self.consumed_output_tokens = 0
        self.consumed_total_tokens = 0

    @property
    def max_tokens(self) -> int:
        return self.max_total_tokens

    @property
    def consumed_tokens(self) -> int:
        return self.consumed_total_tokens

    def check(
        self, estimated_additional: int = 0, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        if self.consumed_total_tokens + estimated_additional > self.max_total_tokens:
            raise BudgetExceededError(
                "total_tokens",
                self.max_total_tokens,
                self.consumed_total_tokens + estimated_additional,
            )
        if input_tokens > 0 and self.consumed_input_tokens + input_tokens > self.max_input_tokens:
            raise BudgetExceededError(
                "input_tokens", self.max_input_tokens, self.consumed_input_tokens + input_tokens
            )
        if (
            output_tokens > 0
            and self.consumed_output_tokens + output_tokens > self.max_output_tokens
        ):
            raise BudgetExceededError(
                "output_tokens", self.max_output_tokens, self.consumed_output_tokens + output_tokens
            )

    def consume(self, count: int, input_tokens: int = 0, output_tokens: int = 0) -> None:
        if input_tokens > 0 or output_tokens > 0:
            self.consumed_input_tokens += max(0, input_tokens)
            self.consumed_output_tokens += max(0, output_tokens)
            self.consumed_total_tokens += max(0, input_tokens + output_tokens)
        else:
            self.consumed_total_tokens += max(0, count)
            # Distribute proportionally for accounting
            self.consumed_input_tokens += int(count * 0.8)
            self.consumed_output_tokens += count - int(count * 0.8)

        if self.consumed_total_tokens > self.max_total_tokens:
            raise BudgetExceededError(
                "total_tokens", self.max_total_tokens, self.consumed_total_tokens
            )
        if self.consumed_input_tokens > self.max_input_tokens:
            raise BudgetExceededError(
                "input_tokens", self.max_input_tokens, self.consumed_input_tokens
            )
        if self.consumed_output_tokens > self.max_output_tokens:
            raise BudgetExceededError(
                "output_tokens", self.max_output_tokens, self.consumed_output_tokens
            )


@dataclass
class CostBudget:
    """Tracks USD expenditure against finite caps."""

    max_cost_usd: float = 2.0
    consumed_cost_usd: float = 0.0

    def check(self, estimated_additional: float = 0.0) -> None:
        if self.consumed_cost_usd + estimated_additional > self.max_cost_usd:
            raise BudgetExceededError(
                "cost", self.max_cost_usd, self.consumed_cost_usd + estimated_additional
            )

    def consume(self, amount: float) -> None:
        self.consumed_cost_usd += max(0.0, amount)
        if self.consumed_cost_usd > self.max_cost_usd:
            raise BudgetExceededError("cost", self.max_cost_usd, self.consumed_cost_usd)


@dataclass
class StepBudget:
    """Tracks executed steps and tool calls against finite bounds."""

    max_steps: int = 20
    max_tool_calls: int = 20
    executed_steps: int = 0
    executed_tool_calls: int = 0

    def check_step(self) -> None:
        if self.executed_steps >= self.max_steps:
            raise BudgetExceededError("step", self.max_steps, self.executed_steps + 1)

    def consume_step(self) -> None:
        self.executed_steps += 1
        if self.executed_steps > self.max_steps:
            raise BudgetExceededError("step", self.max_steps, self.executed_steps)

    def check_tool_call(self) -> None:
        if self.executed_tool_calls >= self.max_tool_calls:
            raise BudgetExceededError(
                "tool_call", self.max_tool_calls, self.executed_tool_calls + 1
            )

    def consume_tool_call(self) -> None:
        self.executed_tool_calls += 1
        if self.executed_tool_calls > self.max_tool_calls:
            raise BudgetExceededError("tool_call", self.max_tool_calls, self.executed_tool_calls)


@dataclass
class TimeBudget:
    """Enforces absolute duration bounds."""

    max_duration_seconds: float = 300.0
    start_time: float = field(default_factory=time.perf_counter)

    def elapsed(self) -> float:
        return time.perf_counter() - self.start_time

    def remaining(self) -> float:
        return max(0.0, self.max_duration_seconds - self.elapsed())

    def check(self) -> None:
        current_elapsed = self.elapsed()
        if current_elapsed >= self.max_duration_seconds:
            raise BudgetExceededError(
                "time_duration", self.max_duration_seconds, round(current_elapsed, 2)
            )


class AgentBudgetManager:
    """Unified manager for Step, Time, Token, and Cost budgets."""

    def __init__(
        self,
        max_steps: int = 20,
        max_tool_calls: int = 20,
        max_duration_seconds: float = 300.0,
        max_tokens: int = 50000,
        max_cost_usd: float = 2.0,
    ) -> None:
        self.step_budget = StepBudget(max_steps=max_steps, max_tool_calls=max_tool_calls)
        self.time_budget = TimeBudget(max_duration_seconds=max_duration_seconds)
        self.token_budget = TokenBudget(max_tokens=max_tokens)
        self.cost_budget = CostBudget(max_cost_usd=max_cost_usd)

    def pre_flight_check(self, estimated_tokens: int = 0, estimated_cost: float = 0.0) -> None:
        """Run verification across all budget dimensions before initiating an operation."""
        self.step_budget.check_step()
        self.step_budget.check_tool_call()
        self.time_budget.check()
        self.token_budget.check(estimated_tokens)
        self.cost_budget.check(estimated_cost)
