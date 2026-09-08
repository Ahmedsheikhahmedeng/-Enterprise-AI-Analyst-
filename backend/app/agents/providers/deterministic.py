"""Deterministic plan generator providing reproducible, test-stable plans without external LLM calls."""

import uuid
from uuid import UUID

from app.agents.schemas import AgentStepSchema, AgentType


class DeterministicAgentPlanner:
    """Generates predictable, strictly bounded plans tailored to profile and goal."""

    async def generate_plan(
        self,
        goal: str,
        agent_type: AgentType,
        datasource_id: UUID | None = None,
        max_steps: int = 20,
    ) -> list[AgentStepSchema]:
        """Generate deterministic steps depending on profile type."""
        clean_goal = goal.strip()
        steps: list[AgentStepSchema] = []

        if agent_type == AgentType.ANALYST_AGENT:
            # Step 1: Query analyst service
            steps.append(
                AgentStepSchema(
                    step_id=str(uuid.uuid4()),
                    sequence=1,
                    tool_name="analyst.query",
                    tool_input={
                        "query": clean_goal,
                        "datasource_id": str(datasource_id) if datasource_id else None,
                    },
                    reason="Analyze user query across structured and unstructured data.",
                    estimated_cost=0.002,
                    estimated_duration=2.0,
                    requires_approval=False,
                )
            )

        elif agent_type == AgentType.RESEARCH_AGENT:
            # Step 1: RAG semantic retrieve
            steps.append(
                AgentStepSchema(
                    step_id=str(uuid.uuid4()),
                    sequence=1,
                    tool_name="rag.retrieve",
                    tool_input={"query": clean_goal, "top_k": 5},
                    reason="Retrieve relevant organizational knowledge and documents.",
                    estimated_cost=0.0015,
                    estimated_duration=1.5,
                    requires_approval=False,
                )
            )

        elif agent_type == AgentType.REPORT_AGENT:
            # Step 1: Query analyst
            steps.append(
                AgentStepSchema(
                    step_id=str(uuid.uuid4()),
                    sequence=1,
                    tool_name="analyst.query",
                    tool_input={
                        "query": clean_goal,
                        "datasource_id": str(datasource_id) if datasource_id else None,
                    },
                    reason="Execute analytical data retrieval prior to report generation.",
                    estimated_cost=0.002,
                    estimated_duration=2.0,
                    requires_approval=False,
                )
            )
            # Step 2: Create report (requires approval for publish/creation)
            dummy_analysis_id = str(uuid.uuid4())
            steps.append(
                AgentStepSchema(
                    step_id=str(uuid.uuid4()),
                    sequence=2,
                    tool_name="report.create",
                    tool_input={
                        "analysis_run_id": dummy_analysis_id,
                        "title": f"Report: {clean_goal[:50]}",
                        "template": "executive",
                    },
                    reason="Compile analytical findings into a formal executive report.",
                    estimated_cost=0.001,
                    estimated_duration=1.0,
                    requires_approval=True,
                )
            )

        elif agent_type == AgentType.EVALUATION_AGENT:
            target_ds = str(datasource_id) if datasource_id else str(uuid.uuid4())
            steps.append(
                AgentStepSchema(
                    step_id=str(uuid.uuid4()),
                    sequence=1,
                    tool_name="evaluation.run",
                    tool_input={"dataset_id": target_ds, "max_cases": 10},
                    reason="Execute benchmark test cases against target evaluation dataset.",
                    estimated_cost=0.005,
                    estimated_duration=5.0,
                    requires_approval=True,
                )
            )

        return steps[:max_steps]


# Backward-compatible alias for deterministic agent planning provider
DeterministicAgentProvider = DeterministicAgentPlanner
