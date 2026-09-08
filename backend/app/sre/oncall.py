"""On-call roster abstractions and escalation policy execution."""

from typing import Any


class EscalationEvaluator:
    """Evaluates escalation policies to determine which responder tier to notify."""

    @staticmethod
    def get_responder_for_step(
        steps: list[dict[str, Any]],
        step_number: int,
    ) -> dict[str, Any] | None:
        """Find escalation step by index (1-indexed)."""
        for step in steps:
            if step.get("step") == step_number:
                return step
        return None
