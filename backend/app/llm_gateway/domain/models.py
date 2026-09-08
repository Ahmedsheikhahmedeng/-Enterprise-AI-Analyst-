"""Domain models and payloads for Enterprise LLM Gateway."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.llm_gateway.domain.enums import (
    CircuitBreakerState,
    DataSensitivity,
    InputTrustLevel,
    LLMTaskType,
    MessageRole,
    ModelCapability,
    ModelStatus,
    RoutingStrategy,
    StreamChunkType,
)


@dataclass
class LLMMessage:
    """Chat message unit tracking role, content, and trust boundary."""

    role: MessageRole
    content: str
    trust_level: InputTrustLevel = InputTrustLevel.USER_INPUT
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptMetadata:
    """Reproducibility metadata capturing prompt identity and template hash."""

    prompt_name: str
    prompt_version: str
    template_hash: str = ""


@dataclass
class ModelPricing:
    """Pricing configuration in USD per 1,000 tokens."""

    input_price_per_1k: Decimal = Decimal("0.0")
    output_price_per_1k: Decimal = Decimal("0.0")

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        """Calculate total estimated cost for token consumption."""
        in_cost = (Decimal(input_tokens) / Decimal(1000)) * self.input_price_per_1k
        out_cost = (Decimal(output_tokens) / Decimal(1000)) * self.output_price_per_1k
        return (in_cost + out_cost).quantize(Decimal("0.000001"))


@dataclass
class ModelDefinition:
    """Governed model entry in the Model Registry."""

    provider: str
    model_name: str
    model_version: str = "latest"
    status: ModelStatus = ModelStatus.ACTIVE
    is_approved: bool = True
    capabilities: set[ModelCapability] = field(default_factory=set)
    pricing: ModelPricing = field(default_factory=ModelPricing)
    context_window: int = 128000
    max_output_tokens: int = 4096
    priority: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TenantLLMPolicy:
    """Organization-level governance policy restricting models and costs."""

    organization_id: UUID
    allowed_providers: list[str] = field(default_factory=list)
    allowed_models: list[str] = field(default_factory=list)
    max_tokens_per_request: int | None = None
    max_cost_per_request: Decimal | None = None
    allowed_capabilities: set[ModelCapability] = field(default_factory=set)
    data_residency: str = "ANY"
    streaming_allowed: bool = True
    caching_allowed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredGenerationRequest:
    """Request envelope enforcing validated structured JSON outputs."""

    schema: dict[str, Any] = field(default_factory=dict)
    pydantic_model: type[BaseModel] | None = None
    strict: bool = True
    max_retries: int = 2
    max_schema_bytes: int = 65536
    max_properties: int = 50
    max_nesting_depth: int = 5
    max_enum_size: int = 100


@dataclass
class LLMRequestPayload:
    """Complete invocation payload routed to target model provider."""

    messages: list[LLMMessage]
    task_type: LLMTaskType
    required_capabilities: set[ModelCapability] = field(default_factory=set)
    routing_strategy: RoutingStrategy = RoutingStrategy.BALANCED
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    pinned_model: str | None = None
    pinned_provider: str | None = None
    temperature: float = 0.0
    max_tokens: int = 2048
    stop_sequences: list[str] = field(default_factory=list)
    prompt_metadata: PromptMetadata | None = None
    idempotency_key: str | None = None
    connect_timeout_s: float = 5.0
    request_timeout_s: float = 30.0
    total_timeout_s: float = 60.0
    structured_request: StructuredGenerationRequest | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponsePayload:
    """Unified response payload returned to consumers."""

    content: str
    provider: str
    model: str
    model_version: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    latency_ms: int
    finish_reason: str = "stop"
    fallback_used: bool = False
    fallback_history: list[str] = field(default_factory=list)
    cache_hit: bool = False
    request_id: str = ""
    parsed_json: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMStreamChunk:
    """Chunk delivered during streaming responses."""

    chunk_type: StreamChunkType
    delta: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error_message: str | None = None


@dataclass
class ProviderHealthStatus:
    """Operational health status of an LLM provider."""

    provider: str
    is_healthy: bool
    latency_ms: int
    failure_rate: float
    circuit_state: CircuitBreakerState
    message: str = ""
