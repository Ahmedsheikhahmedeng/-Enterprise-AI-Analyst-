"""Typed adapter tool wrapping unified AIAnalystService."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import AnalystQueryInput
from app.analyst.service import AIAnalystService
from app.rbac.catalog import PERM_ANALYTICS_EXECUTE


class AnalystTool:
    """Tool executing natural language queries across structured SQL and unstructured RAG."""

    name: str = "analyst.query"
    version: str = "v1.0"
    description: str = (
        "Executes hybrid analytical query across SQL database tables and RAG documents."
    )
    input_schema: type[BaseModel] = AnalystQueryInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_ANALYTICS_EXECUTE
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(self, analyst_service: AIAnalystService | None = None) -> None:
        self.analyst_service = analyst_service or AIAnalystService()

    async def validate(self, tool_input: dict[str, Any]) -> AnalystQueryInput:
        try:
            return AnalystQueryInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, AnalystQueryInput)
            else AnalystQueryInput.model_validate(validated_input)
        )
        return {
            "action": "execute_analyst_query",
            "query": inp.query,
            "datasource_id": str(inp.datasource_id) if inp.datasource_id else None,
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, AnalystQueryInput)
            else AnalystQueryInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()

        result = await self.analyst_service.ask(
            query=inp.query,
            organization_id=context.organization_id,
            session=context.db_session,
            user_id=context.user_id,
            datasource_id=inp.datasource_id,
            limit=inp.limit,
            top_k=inp.top_k,
        )

        duration_ms = (time.perf_counter() - t_start) * 1000

        evidence_items = []
        for ev in result.evidence:
            source_type_str = (
                ev.source_type if isinstance(ev.source_type, str) else str(ev.source_type)
            )
            evidence_items.append(
                {
                    "evidence_id": ev.evidence_id,
                    "source_type": source_type_str,
                    "content": ev.text,
                    "metadata": ev.metadata or {},
                }
            )

        citations_list = [c.get("citation_id") or str(c) for c in result.citations]

        route_val = result.route.value if hasattr(result.route, "value") else str(result.route)
        cost = (
            result.diagnostics.total_cost_usd
            if hasattr(result.diagnostics, "total_cost_usd")
            and result.diagnostics.total_cost_usd > 0
            else 0.002
        )

        return ToolOutput(
            success=bool(result.answer),
            data={
                "answer": result.answer,
                "route_selected": route_val,
                "citations": citations_list,
                "is_degraded": result.is_degraded,
                "analysis_run_id": str(result.analysis_run_id) if result.analysis_run_id else None,
            },
            evidence_items=evidence_items,
            tokens_used=result.diagnostics.branches_executed * 150
            if hasattr(result.diagnostics, "branches_executed")
            else 150,
            cost_usd=cost,
            duration_ms=duration_ms,
            is_degraded=result.is_degraded,
        )
