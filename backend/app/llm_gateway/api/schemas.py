"""Pydantic request and response schemas for LLM Gateway administrative APIs."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.llm_gateway.domain.enums import CircuitBreakerState, ModelStatus


class ModelDefinitionResponse(BaseModel):
    """Schema representing an approved LLM model definition."""

    provider: str
    model_name: str
    model_version: str
    status: ModelStatus
    is_approved: bool
    capabilities: list[str]
    input_price_per_1k: Decimal
    output_price_per_1k: Decimal
    context_window: int
    max_output_tokens: int
    priority: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderHealthResponse(BaseModel):
    """Schema representing operational health of an LLM provider."""

    provider: str
    is_healthy: bool
    latency_ms: int
    failure_rate: float
    circuit_state: CircuitBreakerState
    message: str


class TenantLLMPolicyResponse(BaseModel):
    """Schema representing tenant-level LLM policy and limits."""

    organization_id: UUID
    allowed_providers: list[str]
    allowed_models: list[str]
    max_tokens_per_request: int | None
    max_cost_per_request: Decimal | None
    allowed_capabilities: list[str]
    data_residency: str
    streaming_allowed: bool
    caching_allowed: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateTenantLLMPolicyRequest(BaseModel):
    """Request payload for updating tenant LLM policy."""

    allowed_providers: list[str] | None = None
    allowed_models: list[str] | None = None
    max_tokens_per_request: int | None = None
    max_cost_per_request: Decimal | None = None
    allowed_capabilities: list[str] | None = None
    data_residency: str | None = None
    streaming_allowed: bool | None = None
    caching_allowed: bool | None = None
    metadata: dict[str, Any] | None = None


class LLMUsageRecordResponse(BaseModel):
    """Schema representing a metered LLM request execution record."""

    id: UUID
    provider: str
    model: str
    task_type: str | None
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    latency_ms: int
    status: str
    fallback_used: bool
    cache_hit: bool
    created_at: datetime
