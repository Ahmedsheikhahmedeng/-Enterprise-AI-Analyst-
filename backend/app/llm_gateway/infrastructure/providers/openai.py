"""Production-ready OpenAI HTTP provider adapter for Enterprise LLM Gateway."""

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import httpx

from app.connectors.infrastructure.secrets import get_secret_provider
from app.core.config import get_settings
from app.llm_gateway.domain.enums import (
    CircuitBreakerState,
    MessageRole,
    StreamChunkType,
)
from app.llm_gateway.domain.errors import (
    LLMPolicyViolationError,
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

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """Production adapter for OpenAI and compatible HTTP REST endpoints."""

    def __init__(
        self,
        base_url: str = "https://api.openai.com/v1",
        api_key: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._explicit_key = api_key

    @property
    def provider_name(self) -> str:
        return "openai"

    def _resolve_api_key(self) -> str:
        """Resolve API key using SecretProvider or application settings."""
        if self._explicit_key:
            return self._explicit_key

        settings = get_settings()
        env_key = getattr(settings, "OPENAI_API_KEY", "") or getattr(
            settings, "EMBEDDING_API_KEY", ""
        )
        if not env_key:
            return ""

        raw_str = str(env_key)
        try:
            secret_provider = get_secret_provider()
            return secret_provider.decrypt_value(raw_str)
        except Exception:
            return raw_str

    def _format_messages(self, payload: LLMRequestPayload) -> list[dict[str, str]]:
        formatted = []
        for msg in payload.messages:
            role_str = "user"
            if msg.role == MessageRole.SYSTEM:
                role_str = "system"
            elif msg.role == MessageRole.ASSISTANT:
                role_str = "assistant"
            elif msg.role == MessageRole.TOOL:
                role_str = "tool"
            formatted.append({"role": role_str, "content": msg.content})
        return formatted

    async def generate(self, payload: LLMRequestPayload) -> LLMResponsePayload:
        api_key = self._resolve_api_key()
        if not api_key:
            raise LLMPolicyViolationError("OpenAI API key is missing or not configured.")

        start_time = time.monotonic()
        model_name = payload.pinned_model or "gpt-4o-mini"
        messages = self._format_messages(payload)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
        }
        if payload.stop_sequences:
            body["stop"] = payload.stop_sequences

        timeout = httpx.Timeout(
            connect=payload.connect_timeout_s,
            read=payload.request_timeout_s,
            write=payload.request_timeout_s,
            pool=payload.total_timeout_s,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )

                latency_ms = int((time.monotonic() - start_time) * 1000)

                if resp.status_code == 429:
                    raise LLMRateLimitError("OpenAI rejected request due to rate limits (429).")
                elif resp.status_code in (401, 403):
                    raise LLMPolicyViolationError("Authentication failed with OpenAI API endpoint.")
                elif resp.status_code >= 500:
                    raise LLMProviderError(
                        f"OpenAI service returned server error ({resp.status_code})."
                    )
                elif resp.status_code != 200:
                    raise LLMProviderError(
                        f"OpenAI rejected request with status {resp.status_code}."
                    )

                data = resp.json()
                choice = data["choices"][0]
                content = choice["message"].get("content", "")
                usage = data.get("usage", {})
                in_tokens = usage.get("prompt_tokens", 0)
                out_tokens = usage.get("completion_tokens", 0)

                return LLMResponsePayload(
                    content=content,
                    provider=self.provider_name,
                    model=model_name,
                    model_version="latest",
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    total_tokens=in_tokens + out_tokens,
                    estimated_cost=Decimal("0.0"),
                    latency_ms=latency_ms,
                    finish_reason=choice.get("finish_reason", "stop"),
                    request_id=str(data.get("id", uuid.uuid4())),
                )

        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Request timed out waiting for OpenAI response.") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise LLMProviderError("Network connection error communicating with OpenAI.") from exc

    async def generate_structured(self, payload: LLMRequestPayload) -> LLMResponsePayload:
        """Execute chat completion with JSON schema formatting or structured response validation."""
        api_key = self._resolve_api_key()
        if not api_key:
            raise LLMPolicyViolationError("OpenAI API key is missing or not configured.")

        start_time = time.monotonic()
        model_name = payload.pinned_model or "gpt-4o"
        messages = self._format_messages(payload)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
            "response_format": {"type": "json_object"},
        }

        timeout = httpx.Timeout(
            connect=payload.connect_timeout_s,
            read=payload.request_timeout_s,
            write=payload.request_timeout_s,
            pool=payload.total_timeout_s,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )

                latency_ms = int((time.monotonic() - start_time) * 1000)

                if resp.status_code == 429:
                    raise LLMRateLimitError("OpenAI rejected request due to rate limits (429).")
                elif resp.status_code in (401, 403):
                    raise LLMPolicyViolationError("Authentication failed with OpenAI API endpoint.")
                elif resp.status_code >= 500:
                    raise LLMProviderError(
                        f"OpenAI service returned server error ({resp.status_code})."
                    )
                elif resp.status_code != 200:
                    raise LLMProviderError(
                        f"OpenAI rejected request with status {resp.status_code}."
                    )

                data = resp.json()
                choice = data["choices"][0]
                content = choice["message"].get("content", "")
                usage = data.get("usage", {})
                in_tokens = usage.get("prompt_tokens", 0)
                out_tokens = usage.get("completion_tokens", 0)

                try:
                    parsed = json.loads(content)
                except Exception as exc:
                    raise StructuredOutputValidationError(
                        f"OpenAI response content is not valid JSON: {exc}"
                    ) from exc

                return LLMResponsePayload(
                    content=content,
                    provider=self.provider_name,
                    model=model_name,
                    model_version="latest",
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    total_tokens=in_tokens + out_tokens,
                    estimated_cost=Decimal("0.0"),
                    latency_ms=latency_ms,
                    finish_reason=choice.get("finish_reason", "stop"),
                    request_id=str(data.get("id", uuid.uuid4())),
                    parsed_json=parsed,
                )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Request timed out waiting for OpenAI response.") from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise LLMProviderError("Network connection error communicating with OpenAI.") from exc

    async def generate_stream(self, payload: LLMRequestPayload) -> AsyncIterator[LLMStreamChunk]:
        """Streaming abstraction emitting typed stream chunks."""
        # Yield single-chunk representation for protocol demonstration
        response = await self.generate(payload)
        yield LLMStreamChunk(chunk_type=StreamChunkType.TOKEN, delta=response.content)
        yield LLMStreamChunk(
            chunk_type=StreamChunkType.USAGE,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
        yield LLMStreamChunk(chunk_type=StreamChunkType.FINAL)

    async def health_check(self) -> ProviderHealthStatus:
        api_key = self._resolve_api_key()
        if not api_key:
            return ProviderHealthStatus(
                provider=self.provider_name,
                is_healthy=False,
                latency_ms=0,
                failure_rate=1.0,
                circuit_state=CircuitBreakerState.CLOSED,
                message="OpenAI API key is missing or not configured.",
            )

        start_time = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                latency_ms = int((time.monotonic() - start_time) * 1000)
                if resp.status_code == 200:
                    return ProviderHealthStatus(
                        provider=self.provider_name,
                        is_healthy=True,
                        latency_ms=latency_ms,
                        failure_rate=0.0,
                        circuit_state=CircuitBreakerState.CLOSED,
                        message="OpenAI API endpoint reachable and authenticated.",
                    )
                return ProviderHealthStatus(
                    provider=self.provider_name,
                    is_healthy=False,
                    latency_ms=latency_ms,
                    failure_rate=1.0,
                    circuit_state=CircuitBreakerState.CLOSED,
                    message=f"OpenAI health check returned HTTP {resp.status_code}.",
                )
        except Exception as exc:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            return ProviderHealthStatus(
                provider=self.provider_name,
                is_healthy=False,
                latency_ms=latency_ms,
                failure_rate=1.0,
                circuit_state=CircuitBreakerState.CLOSED,
                message=f"OpenAI health check failed: {exc}",
            )
