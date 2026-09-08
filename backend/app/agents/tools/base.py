"""Base protocol, definitions, and output schemas for Typed Agent Tools."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from app.agents.context import AgentExecutionContext
from app.agents.schemas import ToolRiskLevel


class ToolOutput(BaseModel):
    """Standardized typed envelope for tool execution results."""

    success: bool
    data: dict[str, Any] = {}
    evidence_items: list[dict[str, Any]] = []
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    error_message: str | None = None
    is_degraded: bool = False


@runtime_checkable
class AgentTool(Protocol):
    """Formal protocol implemented by all registered enterprise tools."""

    name: str
    version: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    required_permission: str
    risk_level: ToolRiskLevel
    supports_preview: bool
    supports_approval: bool
    idempotent: bool

    async def validate(self, tool_input: dict[str, Any]) -> BaseModel:
        """Validate input payload against typed Pydantic schema."""
        ...

    async def preview(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> dict[str, Any]:
        """Generate safe, side-effect-free preview of tool execution."""
        ...

    async def execute(
        self, validated_input: BaseModel, context: AgentExecutionContext
    ) -> ToolOutput:
        """Execute tool action through underlying application service."""
        ...
