"""Base interface for agent planning providers."""

import uuid
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.agents.schemas import AgentStepSchema, AgentType


@runtime_checkable
class AgentPlannerProvider(Protocol):
    """Protocol for generating structured execution plans from user goals."""

    async def generate_plan(
        self,
        goal: str,
        agent_type: AgentType,
        datasource_id: UUID | None = None,
        max_steps: int = 20,
    ) -> list[AgentStepSchema]:
        """Generate validated, bounded steps with concise rationale."""
        ...


class OptionalLLMAgentPlanner:
    """LLM planner wrapper that enforces structured schema outputs or falls back safely."""

    def __init__(self, fallback_planner: AgentPlannerProvider | None = None) -> None:
        self.fallback_planner = fallback_planner

    async def generate_plan(
        self,
        goal: str,
        agent_type: AgentType,
        datasource_id: UUID | None = None,
        max_steps: int = 20,
    ) -> list[AgentStepSchema]:
        if self.fallback_planner is not None:
            return await self.fallback_planner.generate_plan(
                goal=goal,
                agent_type=agent_type,
                datasource_id=datasource_id,
                max_steps=max_steps,
            )

        try:
            from app.llm_gateway.application.gateway_service import get_llm_gateway_service
            from app.llm_gateway.domain.enums import (
                InputTrustLevel,
                LLMTaskType,
                MessageRole,
                ModelCapability,
            )
            from app.llm_gateway.domain.models import (
                LLMMessage,
                LLMRequestPayload,
                StructuredGenerationRequest,
            )

            gateway = get_llm_gateway_service()
            messages = [
                LLMMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "You are an enterprise AI planner. Generate a structured multi-step execution plan.\n"
                        "Return a JSON object with 'steps', where each step has 'order', 'tool_name', 'input_parameters', and 'rationale'."
                    ),
                    trust_level=InputTrustLevel.SYSTEM_INSTRUCTION,
                ),
                LLMMessage(
                    role=MessageRole.USER,
                    content=f"Goal: {goal}\nAgent Type: {agent_type.value}\nMax Steps: {max_steps}",
                    trust_level=InputTrustLevel.USER_INPUT,
                ),
            ]

            payload = LLMRequestPayload(
                messages=messages,
                task_type=LLMTaskType.AGENT_REASONING,
                required_capabilities={ModelCapability.CHAT, ModelCapability.STRUCTURED_OUTPUT},
                temperature=0.0,
            )

            structured_req = StructuredGenerationRequest(
                schema={
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "order": {"type": "integer"},
                                    "tool_name": {"type": "string"},
                                    "input_parameters": {"type": "object"},
                                    "rationale": {"type": "string"},
                                },
                                "required": ["order", "tool_name", "input_parameters", "rationale"],
                            },
                        }
                    },
                    "required": ["steps"],
                }
            )

            resp, _ = await gateway.generate_structured(payload, structured_req)
            data = resp.parsed_json or {}
            raw_steps = data.get("steps", [])
            if raw_steps and isinstance(raw_steps, list):
                steps: list[AgentStepSchema] = []
                for s in raw_steps[:max_steps]:
                    steps.append(
                        AgentStepSchema(
                            step_id=str(uuid.uuid4()),
                            sequence=int(s.get("order", s.get("sequence", len(steps) + 1))),
                            tool_name=str(s.get("tool_name", "noop")),
                            tool_input=dict(s.get("input_parameters", s.get("tool_input", {}))),
                            reason=str(
                                s.get("rationale", s.get("reason", "Standard execution step."))
                            ),
                        )
                    )
                if steps:
                    return steps
        except Exception:
            pass

        from app.agents.providers.deterministic import DeterministicAgentPlanner

        return await DeterministicAgentPlanner().generate_plan(
            goal=goal,
            agent_type=agent_type,
            datasource_id=datasource_id,
            max_steps=max_steps,
        )
