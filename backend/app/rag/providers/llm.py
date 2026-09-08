"""HTTP-based LLM generation provider for OpenAI and compatible endpoints."""

import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.rag.exceptions import (
    RAGConfigurationError,
    RAGTimeoutError,
)
from app.rag.providers.base import RAGProviderResponse
from app.rag.providers.local import LocalDeterministicAnswerProvider

logger = logging.getLogger(__name__)


class _StructuredAnswerPayload(BaseModel):
    answer: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    grounded: bool = Field(default=True)


class OpenAILLMProvider:
    """HTTP client invoking OpenAI chat completions API with retries and structured output."""

    def __init__(
        self,
        api_key: str | None,
        model_name: str = "gpt-4o-mini",
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
        fallback: LocalDeterministicAnswerProvider | None = None,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._client = client
        self._owns_client = client is None
        self._fallback = fallback or LocalDeterministicAnswerProvider()

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
            self._owns_client = True
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> RAGProviderResponse:
        """Call chat completions endpoint and parse structured answer."""
        if not self._api_key:
            logger.warning("No API key configured for OpenAI LLM provider; using fallback")
            return await self._fallback.generate(
                system_prompt, user_prompt, max_tokens, temperature
            )

        client = self._get_client()
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_name,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        t0 = time.perf_counter()
        attempt = 0
        last_error: Exception | None = None

        while attempt <= self._max_retries:
            attempt += 1
            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 401:
                    raise RAGConfigurationError("Invalid or unauthorized OpenAI API key.")
                if resp.status_code in (429, 500, 502, 503, 504) and attempt <= self._max_retries:
                    backoff = 1.0 * (attempt**1.5)
                    logger.warning(
                        "LLM API returned %d, retrying in %.1fs...", resp.status_code, backoff
                    )
                    import asyncio

                    await asyncio.sleep(backoff)
                    continue

                resp.raise_for_status()
                data: dict[str, Any] = resp.json()
                raw_content = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})

                in_tokens = usage.get("prompt_tokens", 0)
                out_tokens = usage.get("completion_tokens", 0)

                # Parse JSON content into schema
                parsed_json = json.loads(raw_content)
                validated = _StructuredAnswerPayload.model_validate(parsed_json)

                latency_ms = (time.perf_counter() - t0) * 1000
                return RAGProviderResponse(
                    answer=validated.answer,
                    evidence_ids=validated.evidence_ids,
                    confidence=validated.confidence,
                    grounded=validated.grounded,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    model=self._model_name,
                    latency_ms=latency_ms,
                )

            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt <= self._max_retries:
                    continue
                raise RAGTimeoutError(
                    f"LLM request timed out after {self._timeout_seconds}s"
                ) from exc
            except (httpx.HTTPStatusError, json.JSONDecodeError, KeyError) as exc:
                last_error = exc
                logger.warning(
                    "LLM request failed or returned invalid JSON (%s); using fallback", exc
                )
                return await self._fallback.generate(
                    system_prompt, user_prompt, max_tokens, temperature
                )
            except Exception as exc:
                last_error = exc
                break

        logger.error("LLM generation failed after %d attempts: %s", attempt, last_error)
        return await self._fallback.generate(system_prompt, user_prompt, max_tokens, temperature)
