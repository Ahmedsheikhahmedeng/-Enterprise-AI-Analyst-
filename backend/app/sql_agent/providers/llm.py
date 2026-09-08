"""HTTP-based LLM SQL generation provider for OpenAI and compatible APIs."""

import time

import httpx
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.sql_agent.exceptions import SQLConfigurationError, SQLProviderError, SQLTimeoutError
from app.sql_agent.models import GeneratedSQL, SchemaContext
from app.sql_agent.planner import SQLPlan
from app.sql_agent.providers.base import SQLProviderResponse
from app.sql_agent.providers.deterministic import DeterministicSQLProvider

logger = get_logger("sql_agent.provider.llm")


class _StructuredSQLPayload(BaseModel):
    sql: str = Field(..., description="PostgreSQL read-only SELECT query")
    tables_used: list[str] = Field(default_factory=list)
    columns_used: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    explanation: str | None = Field(default=None)


class OpenAISQLProvider:
    """HTTP LLM provider generating structured SQL using OpenAI chat completions."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self._model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._fallback_provider = DeterministicSQLProvider(model_name=f"{model_name}-fallback")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def generate_sql(
        self,
        plan: SQLPlan,
        schema_context: SchemaContext,
    ) -> SQLProviderResponse:
        """Execute chat completion request with strict schema prompting and JSON output format."""
        if not self.api_key:
            logger.warning(
                "No API key configured for OpenAI SQL provider; using deterministic fallback"
            )
            return await self._fallback_provider.generate_sql(plan, schema_context)

        t0 = time.perf_counter()
        schema_ddl = schema_context.format_ddl_representation()

        system_prompt = (
            "You are a secure, read-only Enterprise PostgreSQL database analyst.\n"
            "Given a user question and verified database schema, you must generate a\n"
            "syntactically correct PostgreSQL query.\n\n"
            "MANDATORY SECURITY & OPERATIONAL RULES:\n"
            "1. READ-ONLY: Generate ONLY SELECT or WITH (CTE) queries.\n"
            "2. FORBIDDEN: NEVER output INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, or CREATE.\n"
            "3. SCHEMA BOUNDARIES: Use ONLY tables and columns explicitly declared in the schema.\n"
            "4. NO MULTI-STATEMENT: Output exactly one single logical query statement.\n"
            "5. NO DANGEROUS FUNCTIONS: Never call system, administrative, or file functions.\n"
            "6. OUTPUT FORMAT: Respond strictly with a JSON object adhering to this schema:\n"
            "{\n"
            '  "sql": "SELECT ...",\n'
            '  "tables_used": ["sales"],\n'
            '  "columns_used": ["quarter", "revenue"],\n'
            '  "confidence": 0.95,\n'
            '  "explanation": "Calculates quarterly revenue aggregate."\n'
            "}"
        )

        user_content = (
            f"<schema>\n{schema_ddl}\n</schema>\n\n"
            f"<user_question>\n{plan.question}\n</user_question>\n"
            f"Dialect: {schema_context.dialect}\n"
            f"Max Rows: {plan.max_limit}"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
        }

        last_exc: Exception | None = None
        for _attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers,
                        json=body,
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    raw_choice = data["choices"][0]["message"]["content"]
                    usage = data.get("usage", {})

                    parsed_payload = _StructuredSQLPayload.model_validate_json(raw_choice)
                    latency = (time.perf_counter() - t0) * 1000

                    return SQLProviderResponse(
                        generated_sql=GeneratedSQL(
                            sql=parsed_payload.sql,
                            dialect=schema_context.dialect,
                            tables_used=parsed_payload.tables_used,
                            columns_used=parsed_payload.columns_used,
                            confidence=parsed_payload.confidence,
                            explanation=parsed_payload.explanation,
                        ),
                        input_tokens=usage.get("prompt_tokens", 0),
                        output_tokens=usage.get("completion_tokens", 0),
                        model=self._model_name,
                        latency_ms=latency,
                    )

                if resp.status_code in (401, 403):
                    raise SQLConfigurationError(
                        f"Authentication failed with LLM API: {resp.status_code}"
                    )
                if resp.status_code >= 500 or resp.status_code == 429:
                    last_exc = SQLProviderError(
                        f"LLM API temporary failure ({resp.status_code}): {resp.text}"
                    )
                    continue

                raise SQLProviderError(f"LLM API rejected query ({resp.status_code}): {resp.text}")

            except httpx.TimeoutException:
                last_exc = SQLTimeoutError("LLM API generation timed out.")
            except (SQLConfigurationError, SQLProviderError):
                raise
            except Exception as exc:
                last_exc = exc

        logger.warning(
            "OpenAI SQL generation failed after retries; falling back to deterministic generator",
            error=str(last_exc),
        )
        return await self._fallback_provider.generate_sql(plan, schema_context)
