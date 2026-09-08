"""Deterministic LLM Provider implementation for offline execution and test simulation."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

from app.llm_gateway.domain.enums import (
    CircuitBreakerState,
    LLMTaskType,
    StreamChunkType,
)
from app.llm_gateway.domain.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    StructuredOutputValidationError,
)
from app.llm_gateway.domain.models import (
    LLMRequestPayload,
    LLMResponsePayload,
    LLMStreamChunk,
    ProviderHealthStatus,
)
from app.llm_gateway.domain.protocols import LLMProvider


class DeterministicLLMProvider(LLMProvider):
    """Offline, deterministic provider simulating realistic LLM responses and failure modes."""

    def __init__(
        self,
        *,
        fixed_response: str | None = None,
        fixed_structured_response: dict[str, Any] | None = None,
        simulate_timeout: bool = False,
        simulate_rate_limit: bool = False,
        simulate_provider_failure: bool = False,
        simulate_malformed_json: bool = False,
        latency_ms: int = 5,
    ) -> None:
        self.fixed_response = fixed_response
        self.fixed_structured_response = fixed_structured_response
        self.simulate_timeout = simulate_timeout
        self.simulate_rate_limit = simulate_rate_limit
        self.simulate_provider_failure = simulate_provider_failure
        self.simulate_malformed_json = simulate_malformed_json
        self.latency_ms = latency_ms

    @property
    def provider_name(self) -> str:
        return "deterministic"

    def _check_injected_failures(self) -> None:
        if self.simulate_timeout:
            raise LLMTimeoutError("Simulated provider timeout exceeded.")
        if self.simulate_rate_limit:
            raise LLMRateLimitError("Simulated 429 Too Many Requests rate limit.")
        if self.simulate_provider_failure:
            raise LLMProviderError("Simulated 500 Internal Server Error.")

    def _synthesize_task_response(self, payload: LLMRequestPayload) -> str:
        if self.fixed_response is not None:
            return self.fixed_response

        # Synthetic fallback based on task_type
        if payload.task_type == LLMTaskType.RAG_ANSWER:
            return "Based on the provided documents, the requested information indicates positive quarterly growth."
        elif payload.task_type == LLMTaskType.SQL_GENERATION:
            return json.dumps(
                {
                    "sql": "SELECT city, SUM(revenue) FROM orders GROUP BY city;",
                    "confidence": 0.95,
                    "explanation": "Aggregated revenue by city from orders table.",
                }
            )
        elif payload.task_type == LLMTaskType.EVALUATION_JUDGE:
            return json.dumps(
                {
                    "score": 0.95,
                    "label": "excellent",
                    "reason": "Answer strongly supported by evidence.",
                }
            )
        elif payload.task_type == LLMTaskType.ANALYST_REASONING:
            return "Analysis complete: metrics evaluated across selected dimensions."
        return "Deterministic response generated successfully."

    async def generate(self, payload: LLMRequestPayload) -> LLMResponsePayload:
        self._check_injected_failures()
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        content = self._synthesize_task_response(payload)
        in_tokens = max(10, sum(len(m.content.split()) for m in payload.messages))
        out_tokens = max(10, len(content.split()))

        return LLMResponsePayload(
            content=content,
            provider=self.provider_name,
            model=payload.pinned_model or "mock-model",
            model_version="1.0",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=in_tokens + out_tokens,
            estimated_cost=Decimal("0.0"),
            latency_ms=self.latency_ms,
            finish_reason="stop",
            fallback_used=False,
            request_id=str(uuid.uuid4()),
        )

    async def generate_structured(self, payload: LLMRequestPayload) -> LLMResponsePayload:
        self._check_injected_failures()
        if self.simulate_malformed_json:
            raise StructuredOutputValidationError(
                "Simulated malformed JSON response: {invalid-json"
            )

        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000.0)

        data = self.fixed_structured_response
        if data is None:
            if payload.task_type == LLMTaskType.SQL_GENERATION:
                data = {
                    "sql": "SELECT id, name FROM customers;",
                    "confidence": 0.98,
                    "explanation": "Structured SQL query plan.",
                }
            elif payload.task_type == LLMTaskType.EVALUATION_JUDGE:
                data = {
                    "score": 0.92,
                    "label": "excellent",
                    "reason": "Structured evaluation scoring verified.",
                }
            else:
                data = {"status": "success", "result": "Structured payload verified."}

        content = json.dumps(data)
        in_tokens = max(10, sum(len(m.content.split()) for m in payload.messages))
        out_tokens = max(10, len(content.split()))

        return LLMResponsePayload(
            content=content,
            provider=self.provider_name,
            model=payload.pinned_model or "mock-model",
            model_version="1.0",
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=in_tokens + out_tokens,
            estimated_cost=Decimal("0.0"),
            latency_ms=self.latency_ms,
            finish_reason="stop",
            fallback_used=False,
            request_id=str(uuid.uuid4()),
            parsed_json=data,
        )

    async def generate_stream(self, payload: LLMRequestPayload) -> AsyncIterator[LLMStreamChunk]:
        self._check_injected_failures()
        text = self._synthesize_task_response(payload)
        tokens = text.split(" ")
        for token in tokens:
            if self.latency_ms > 0:
                await asyncio.sleep(self.latency_ms / 1000.0)
            yield LLMStreamChunk(chunk_type=StreamChunkType.TOKEN, delta=token + " ")

        yield LLMStreamChunk(
            chunk_type=StreamChunkType.USAGE,
            input_tokens=len(payload.messages) * 10,
            output_tokens=len(tokens),
        )
        yield LLMStreamChunk(chunk_type=StreamChunkType.FINAL)

    async def health_check(self) -> ProviderHealthStatus:
        if self.simulate_provider_failure or self.simulate_timeout:
            return ProviderHealthStatus(
                provider=self.provider_name,
                is_healthy=False,
                latency_ms=self.latency_ms,
                failure_rate=1.0,
                circuit_state=CircuitBreakerState.OPEN,
                message="Deterministic failure simulation active",
            )
        return ProviderHealthStatus(
            provider=self.provider_name,
            is_healthy=True,
            latency_ms=self.latency_ms,
            failure_rate=0.0,
            circuit_state=CircuitBreakerState.CLOSED,
            message="Deterministic mock provider is operational",
        )
