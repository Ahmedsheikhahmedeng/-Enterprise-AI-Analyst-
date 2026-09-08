"""Agent Tool wrapping ResponseOrchestrationService for autonomous agents."""

import contextlib
import time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolExecutionError, ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.rbac.catalog import PERM_ORCHESTRATION_EXECUTE
from app.response_orchestration.domain.enums import OrchestrationMode
from app.response_orchestration.domain.models import EnterpriseQueryRequest


class AskEnterpriseToolInput(BaseModel):
    """Input payload for enterprise question orchestration tool."""

    question: str = Field(
        ..., min_length=2, max_length=2000, description="Natural language enterprise question"
    )
    mode: str = Field(default="AUTO", description="Routing mode: AUTO, RAG, SQL, HYBRID, GRAPH")
    target_dataset_id: str | None = Field(default=None, description="Optional target dataset UUID")

    model_config = ConfigDict(extra="forbid")


class AskEnterpriseTool:
    """Agent tool providing access to the canonical Enterprise Response Orchestrator."""

    name: str = "orchestrator.ask"
    version: str = "v1.0"
    description: str = "Asks a multi-modal enterprise question orchestrating RAG, SQL, Semantics, and Knowledge Graph."
    input_schema: type[BaseModel] = AskEnterpriseToolInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_ORCHESTRATION_EXECUTE
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(self, orchestration_service: Any = None) -> None:
        self.orchestration_service = orchestration_service

    async def validate(self, tool_input: dict[str, Any]) -> AskEnterpriseToolInput:
        """Validate input payload against typed Pydantic schema."""
        try:
            return AskEnterpriseToolInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        """Generate safe preview of tool execution."""
        inp = (
            validated_input
            if isinstance(validated_input, AskEnterpriseToolInput)
            else AskEnterpriseToolInput.model_validate(validated_input)
        )
        return {
            "tool": self.name,
            "action": "orchestrate_query",
            "question": inp.question,
            "mode": inp.mode,
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        """Execute enterprise orchestration query within agent session boundary."""
        inp = (
            validated_input
            if isinstance(validated_input, AskEnterpriseToolInput)
            else AskEnterpriseToolInput.model_validate(validated_input)
        )
        t0 = time.perf_counter()

        # Lazy service resolution
        service = self.orchestration_service
        if service is None:
            from app.response_orchestration.application.orchestration_service import (
                ResponseOrchestrationService,
            )

            service = ResponseOrchestrationService()

        mode_enum = OrchestrationMode.AUTO
        with contextlib.suppress(Exception):
            mode_enum = OrchestrationMode(inp.mode.upper())

        ds_id = None
        if inp.target_dataset_id:
            with contextlib.suppress(Exception):
                ds_id = UUID(inp.target_dataset_id)

        req = EnterpriseQueryRequest(
            question=inp.question,
            organization_id=context.organization_id,
            user_id=context.user_id or context.session_id,
            conversation_id=None,
            mode=mode_enum,
            target_dataset_id=ds_id,
        )

        try:
            res = await service.ask(request=req, session=context.db_session)
            duration_ms = (time.perf_counter() - t0) * 1000
            return ToolOutput(
                success=True,
                data={
                    "answer": res.answer,
                    "decision": res.decision.value,
                    "confidence": res.confidence_score,
                    "status": res.status.value,
                    "citations": [c.citation_id for c in res.citations],
                    "warnings": res.warnings,
                },
                duration_ms=duration_ms,
            )
        except Exception as exc:
            raise ToolExecutionError(
                self.name, f"orchestrator.ask execution failed: {exc}"
            ) from exc
