"""Validation of generated execution plans before execution starts."""

from app.agents.exceptions import PlanValidationError
from app.agents.schemas import AgentStepSchema


class AgentPlanValidator:
    """Validates structural correctness, known tools, budget bounds, and rationale format."""

    def __init__(
        self,
        registered_tools: set[str],
        max_steps: int = 20,
        max_tokens: int = 50000,
        max_cost_usd: float = 2.0,
    ) -> None:
        self.registered_tools = registered_tools
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.max_cost_usd = max_cost_usd

    def validate(
        self,
        steps: list[AgentStepSchema],
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> None:
        """Validate proposed plan against safety bounds; raises PlanValidationError on failure."""
        if not steps:
            raise PlanValidationError("Execution plan contains no steps.")

        if len(steps) > self.max_steps:
            raise PlanValidationError(
                f"Plan exceeds step limit: {len(steps)} steps proposed, maximum allowed is {self.max_steps}."
            )

        if estimated_tokens > self.max_tokens:
            raise PlanValidationError(
                f"Plan exceeds estimated token limit: {estimated_tokens} > {self.max_tokens}."
            )

        if estimated_cost > self.max_cost_usd:
            raise PlanValidationError(
                f"Plan exceeds estimated cost limit: ${estimated_cost:.2f} > ${self.max_cost_usd:.2f}."
            )

        seen_sequences: set[int] = set()
        for idx, step in enumerate(steps, start=1):
            # Sequence ordering check
            if step.sequence != idx:
                raise PlanValidationError(
                    f"Step sequence mismatch at index {idx}: expected sequence {idx}, got {step.sequence}."
                )
            if step.sequence in seen_sequences:
                raise PlanValidationError(f"Duplicate step sequence {step.sequence} encountered.")
            seen_sequences.add(step.sequence)

            # Tool registry existence check
            if step.tool_name not in self.registered_tools:
                raise PlanValidationError(
                    f"Unknown tool '{step.tool_name}' in step {step.sequence}. Must be one of: {sorted(self.registered_tools)}"
                )

            # Reason validation: concise action rationale, NO CoT or private thoughts
            if not step.reason or len(step.reason.strip()) < 3:
                raise PlanValidationError(
                    f"Step {step.sequence} must provide a concise action rationale."
                )
            if len(step.reason) > 500:
                raise PlanValidationError(
                    f"Step {step.sequence} rationale too verbose ({len(step.reason)} chars). Max 500 chars allowed."
                )
