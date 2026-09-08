"""Base protocol abstraction and data types for SQL generation providers."""

from dataclasses import dataclass
from typing import Protocol

from app.sql_agent.models import GeneratedSQL, SchemaContext
from app.sql_agent.planner import SQLPlan


@dataclass(frozen=True)
class SQLProviderResponse:
    """Standardized response emitted by SQL generation providers."""

    generated_sql: GeneratedSQL
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "deterministic"
    latency_ms: float = 0.0


class SQLGenerationProvider(Protocol):
    """Protocol contract for text-to-SQL generation providers."""

    @property
    def provider_name(self) -> str:
        """Return provider identifier name."""
        ...

    @property
    def model_name(self) -> str:
        """Return active model name."""
        ...

    async def generate_sql(
        self,
        plan: SQLPlan,
        schema_context: SchemaContext,
    ) -> SQLProviderResponse:
        """Generate SQL statement based on analytical plan and verified schema context."""
        ...
