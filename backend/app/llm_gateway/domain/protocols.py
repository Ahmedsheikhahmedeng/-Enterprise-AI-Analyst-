"""Protocols and interfaces for LLM provider adapters."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from app.llm_gateway.domain.models import (
    LLMRequestPayload,
    LLMResponsePayload,
    LLMStreamChunk,
    ProviderHealthStatus,
)


@runtime_checkable
class LLMProvider(Protocol):
    """Unified interface required for all external and synthetic LLM provider adapters."""

    @property
    def provider_name(self) -> str:
        """Identifier of the provider (e.g. 'openai', 'deterministic')."""
        ...

    async def generate(self, payload: LLMRequestPayload) -> LLMResponsePayload:
        """Execute chat completion and return unified response payload."""
        ...

    async def generate_structured(self, payload: LLMRequestPayload) -> LLMResponsePayload:
        """Execute structured JSON generation with schema compliance."""
        ...

    def generate_stream(self, payload: LLMRequestPayload) -> AsyncIterator[LLMStreamChunk]:
        """Stream response chunks asynchronously."""
        ...

    async def health_check(self) -> ProviderHealthStatus:
        """Perform non-invasive operational health check."""
        ...
