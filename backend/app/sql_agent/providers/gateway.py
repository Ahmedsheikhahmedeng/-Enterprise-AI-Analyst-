"""SQL generation provider routing through Enterprise LLM Gateway."""

import time
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

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
from app.sql_agent.models import GeneratedSQL, SchemaContext
from app.sql_agent.planner import SQLPlan
from app.sql_agent.providers.base import SQLGenerationProvider, SQLProviderResponse


class StructuredSQLSchema(BaseModel):
    """Pydantic schema for structured SQL query plan generation."""

    sql: str = Field(..., description="PostgreSQL read-only SELECT query")
    tables_used: list[str] = Field(default_factory=list)
    columns_used: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    explanation: str | None = Field(default=None)


class GatewaySQLProvider(SQLGenerationProvider):
    """SQL generation adapter executing through central LLMGatewayService."""

    def __init__(
        self,
        gateway_service: Any = None,
        model_name: str = "gpt-4o-mini",
    ) -> None:
        if gateway_service is None:
            from app.llm_gateway.application.gateway_service import get_llm_gateway_service

            self._gateway = get_llm_gateway_service()
        else:
            self._gateway = gateway_service
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "gateway"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _build_system_prompt(self, schema_context: SchemaContext) -> str:
        schema_text = schema_context.format_ddl_representation()

        return (
            "You are an enterprise SQL generation engine for PostgreSQL.\n"
            "Generate syntactically correct, read-only SELECT queries strictly adhering to the schema.\n"
            "Rules:\n"
            "- Only generate SELECT queries.\n"
            "- Never modify, drop, or update data.\n"
            "- Fully qualify or alias table names.\n"
            "- Use provided joins and foreign keys where available.\n\n"
            f"Available Database Schema:\n{schema_text}"
        )

    def _build_user_prompt(self, plan: SQLPlan) -> str:
        return (
            f"User Question: {plan.question}\n"
            f"Target Tables: {', '.join(plan.target_tables)}\n"
            f"Suggested Aggregations: {', '.join(plan.suggested_aggregations) if plan.suggested_aggregations else 'None'}\n"
            f"Filter Hints: {', '.join(plan.filter_hints) if plan.filter_hints else 'None'}\n"
            f"Max Rows Limit: {plan.max_limit}\n"
            "Return output strictly conforming to the requested JSON schema."
        )

    async def generate_sql(
        self,
        plan: SQLPlan,
        schema_context: SchemaContext,
    ) -> SQLProviderResponse:
        system_prompt = self._build_system_prompt(schema_context)
        user_prompt = self._build_user_prompt(plan)

        messages = [
            LLMMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
                trust_level=InputTrustLevel.SYSTEM_INSTRUCTION,
            ),
            LLMMessage(
                role=MessageRole.USER,
                content=user_prompt,
                trust_level=InputTrustLevel.USER_INPUT,
            ),
        ]

        payload = LLMRequestPayload(
            messages=messages,
            task_type=LLMTaskType.SQL_GENERATION,
            required_capabilities={ModelCapability.CHAT, ModelCapability.STRUCTURED_OUTPUT},
            pinned_model=self._model_name if self._model_name != "auto" else None,
            temperature=0.0,
        )

        structured_req = StructuredGenerationRequest(
            schema=StructuredSQLSchema.model_json_schema(),
            pydantic_model=StructuredSQLSchema,
            strict=True,
        )

        t_start = time.perf_counter()
        response, parsed_model = await self._gateway.generate_structured(
            payload=payload,
            structured_req=structured_req,
        )
        latency_ms = (time.perf_counter() - t_start) * 1000

        if isinstance(parsed_model, StructuredSQLSchema):
            query = parsed_model.sql
            explanation = parsed_model.explanation
            confidence = parsed_model.confidence
            tables_used = parsed_model.tables_used
            columns_used = parsed_model.columns_used
        else:
            raw_data = response.parsed_json or {}
            query = str(raw_data.get("sql", "SELECT 1;"))
            explanation = raw_data.get("explanation")
            confidence = float(raw_data.get("confidence", 0.9))
            tables_used = list(raw_data.get("tables_used", []))
            columns_used = list(raw_data.get("columns_used", []))

        generated_sql = GeneratedSQL(
            sql=query,
            dialect=schema_context.dialect,
            explanation=explanation,
            confidence=confidence,
            tables_used=tables_used,
            columns_used=columns_used,
        )

        return SQLProviderResponse(
            generated_sql=generated_sql,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            model=response.model,
            latency_ms=latency_ms,
        )
