"""OpenAI embedding provider implementation using direct HTTP calls."""

import asyncio
import logging
from collections.abc import Sequence
from typing import Any

import httpx

from app.embeddings.exceptions import (
    EmbeddingAuthenticationError,
    EmbeddingConfigurationError,
    EmbeddingInvalidInputError,
    EmbeddingProviderError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
)
from app.embeddings.models import EmbeddingVector
from app.embeddings.providers.base import ProviderEmbeddingResponse

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider:
    """HTTP-based OpenAI Embedding Provider decoupled from external vendor SDKs.

    Communicates directly with OpenAI or compatible REST endpoints (vLLM, Ollama, Azure)
    using httpx.AsyncClient with explicit timeout, concurrency control, and exponential backoff.
    """

    def __init__(
        self,
        api_key: str | None,
        model_name: str = "text-embedding-3-small",
        dimensions: int = 1536,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_backoff_factor: float = 1.5,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise EmbeddingConfigurationError(
                "OpenAI API key is missing. Set EMBEDDING_API_KEY environment variable."
            )
        self._api_key = api_key
        self._model_name = model_name
        self._dimensions = dimensions
        self._base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._retry_backoff_factor = retry_backoff_factor
        self._client = client
        self._owns_client = client is None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or getattr(self._client, "is_closed", False) is True:
            self._client = httpx.AsyncClient(timeout=self._timeout_seconds)
            self._owns_client = True
        return self._client

    async def close(self) -> None:
        if (
            self._owns_client
            and self._client is not None
            and getattr(self._client, "is_closed", False) is False
        ):
            await self._client.aclose()

    async def embed_texts(
        self,
        texts: Sequence[str],
    ) -> ProviderEmbeddingResponse:
        """Send a batch of texts to the embeddings endpoint with retry logic."""
        if not texts:
            return ProviderEmbeddingResponse(vectors=[], prompt_tokens=0, total_tokens=0)

        endpoint = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self._model_name,
            "input": list(texts),
        }
        # text-embedding-3 models support dimension reduction / parameter
        if "text-embedding-3" in self._model_name:
            payload["dimensions"] = self._dimensions

        client = await self._get_client()
        attempt = 0
        last_error: Exception | None = None

        while attempt <= self._max_retries:
            try:
                response = await client.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout_seconds,
                )

                # Check HTTP status
                if response.status_code == 200:
                    data = response.json()
                    raw_items = data.get("data", [])
                    # Strict ordering preservation using index
                    sorted_items = sorted(raw_items, key=lambda x: x.get("index", 0))
                    vectors: list[EmbeddingVector] = [item["embedding"] for item in sorted_items]

                    usage = data.get("usage", {})
                    prompt_tokens = usage.get("prompt_tokens", 0)
                    total_tokens = usage.get("total_tokens", prompt_tokens)

                    return ProviderEmbeddingResponse(
                        vectors=vectors,
                        prompt_tokens=prompt_tokens,
                        total_tokens=total_tokens,
                        metadata={"provider": "openai", "model": self._model_name},
                    )

                # Non-retryable client errors
                if response.status_code == 401:
                    raise EmbeddingAuthenticationError(
                        "Authentication failed with OpenAI embedding provider.",
                        provider="openai",
                        status_code=401,
                    )
                if response.status_code == 400:
                    err_msg = response.text
                    raise EmbeddingInvalidInputError(
                        f"OpenAI rejected embedding input (400 Bad Request): {err_msg}"
                    )

                # Rate limits (429) and Server errors (5xx) are retryable
                if response.status_code == 429:
                    retry_after_hdr = response.headers.get("Retry-After")
                    retry_after = float(retry_after_hdr) if retry_after_hdr else None
                    if attempt == self._max_retries:
                        raise EmbeddingRateLimitError(
                            "OpenAI embedding rate limit exceeded after retries.",
                            provider="openai",
                            retry_after=retry_after,
                        )
                    sleep_time = retry_after or (self._retry_backoff_factor * (2**attempt))
                    logger.warning(
                        f"Rate limited by OpenAI (429). Retrying in {sleep_time:.2f}s "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                    await asyncio.sleep(sleep_time)
                    attempt += 1
                    continue

                if response.status_code >= 500:
                    if attempt == self._max_retries:
                        err_msg = (
                            f"OpenAI server error ({response.status_code}) after retries: "
                            f"{response.text}"
                        )
                        raise EmbeddingProviderError(
                            err_msg,
                            provider="openai",
                            status_code=response.status_code,
                        )
                    sleep_time = self._retry_backoff_factor * (2**attempt)
                    logger.warning(
                        "OpenAI server error (%d). Retrying in %.2fs (attempt %d/%d)",
                        response.status_code,
                        sleep_time,
                        attempt + 1,
                        self._max_retries,
                    )
                    await asyncio.sleep(sleep_time)
                    attempt += 1
                    continue

                # Unexpected status code
                raise EmbeddingProviderError(
                    f"Unexpected status {response.status_code} from OpenAI: {response.text}",
                    provider="openai",
                    status_code=response.status_code,
                )

            except httpx.TimeoutException as exc:
                last_error = EmbeddingTimeoutError(
                    f"Request to OpenAI embedding timed out after {self._timeout_seconds}s.",
                    provider="openai",
                )
                if attempt == self._max_retries:
                    raise last_error from exc
                sleep_time = self._retry_backoff_factor * (2**attempt)
                logger.warning(
                    "Timeout on OpenAI embedding request. Retrying in %.2fs...",
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)
                attempt += 1

            except (EmbeddingAuthenticationError, EmbeddingInvalidInputError):
                raise

            except Exception as exc:
                if isinstance(exc, (EmbeddingRateLimitError, EmbeddingProviderError)):
                    raise
                last_error = EmbeddingProviderError(
                    f"Network or connection error communicating with OpenAI: {exc}",
                    provider="openai",
                )
                if attempt == self._max_retries:
                    raise last_error from exc
                sleep_time = self._retry_backoff_factor * (2**attempt)
                await asyncio.sleep(sleep_time)
                attempt += 1

        if last_error:
            raise last_error
        raise EmbeddingProviderError("Failed to obtain embeddings from OpenAI.", provider="openai")

    async def health_check(self) -> bool:
        """Check provider connectivity with a lightweight ping or model check."""
        try:
            client = await self._get_client()
            endpoint = f"{self._base_url}/models/{self._model_name}"
            headers = {"Authorization": f"Bearer {self._api_key}"}
            res = await client.get(endpoint, headers=headers, timeout=5.0)
            return res.status_code == 200
        except Exception:
            return False
