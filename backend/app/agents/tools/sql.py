"""Typed adapter tool wrapping SQLAgentService."""

import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agents.context import AgentExecutionContext
from app.agents.exceptions import ToolInputValidationError
from app.agents.schemas import ToolRiskLevel
from app.agents.tools.base import ToolOutput
from app.agents.tools.schemas import SQLQueryInput
from app.rbac.catalog import PERM_ANALYTICS_EXECUTE
from app.sql_agent.service import SQLAgentService


class SQLTool:
    """Tool executing safe read-only SQL queries over validated data sources."""

    name: str = "sql.query"
    version: str = "v1.0"
    description: str = "Executes structured SQL analysis on relational database tables."
    input_schema: type[BaseModel] = SQLQueryInput
    output_schema: type[BaseModel] = ToolOutput
    required_permission: str = PERM_ANALYTICS_EXECUTE
    risk_level: ToolRiskLevel = ToolRiskLevel.READ
    supports_preview: bool = True
    supports_approval: bool = False
    idempotent: bool = True

    def __init__(self, sql_service: SQLAgentService | None = None) -> None:
        self.sql_service = sql_service or SQLAgentService()

    async def validate(self, tool_input: dict[str, Any]) -> SQLQueryInput:
        try:
            return SQLQueryInput.model_validate(tool_input)
        except ValidationError as exc:
            raise ToolInputValidationError(self.name, str(exc), exc.errors()) from exc

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        inp = (
            validated_input
            if isinstance(validated_input, SQLQueryInput)
            else SQLQueryInput.model_validate(validated_input)
        )
        return {
            "action": "execute_sql_query",
            "question": inp.question,
            "datasource_id": str(inp.datasource_id),
            "organization_id": str(context.organization_id),
        }

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        inp = (
            validated_input
            if isinstance(validated_input, SQLQueryInput)
            else SQLQueryInput.model_validate(validated_input)
        )
        t_start = time.perf_counter()

        result = await self.sql_service.execute_question(
            question=inp.question,
            datasource_id=inp.datasource_id,
            organization_id=context.organization_id,
            session=context.db_session,
            user_id=context.user_id,
            limit=inp.limit,
            analyze=True,
        )

        duration_ms = (time.perf_counter() - t_start) * 1000

        rows = result.query_result.rows if result.query_result else []
        row_count = result.query_result.row_count if result.query_result else len(rows)
        summary = result.analysis.summary if result.analysis else "SQL executed successfully."

        evidence_items = []
        if rows:
            evidence_items.append(
                {
                    "evidence_id": "S1",
                    "source_type": "sql",
                    "content": str(rows[:5])[:1000],
                    "metadata": {
                        "datasource_id": str(inp.datasource_id),
                        "sql": result.generated_sql,
                        "row_count": row_count,
                    },
                }
            )

        return ToolOutput(
            success=True,
            data={
                "sql": result.generated_sql,
                "summary": summary,
                "row_count": row_count,
            },
            evidence_items=evidence_items,
            tokens_used=result.diagnostics.get("tokens", 100) if result.diagnostics else 100,
            cost_usd=0.001,
            duration_ms=duration_ms,
        )
