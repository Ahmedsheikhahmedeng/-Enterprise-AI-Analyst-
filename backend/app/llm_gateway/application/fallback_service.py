"""Fallback orchestration, retry backoff, and circuit breaker management."""

import asyncio
import logging
import random
import time

from app.llm_gateway.domain.enums import CircuitBreakerState
from app.llm_gateway.domain.errors import (
    LLMError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    NoHealthyProviderError,
    SecurityViolationError,
    TenantPolicyViolationError,
)
from app.llm_gateway.domain.models import (
    LLMRequestPayload,
    LLMResponsePayload,
    ModelDefinition,
)
from app.llm_gateway.infrastructure.registry import ProviderRegistry

logger = logging.getLogger(__name__)


class ProviderCircuitBreaker:
    """Tracks provider failure rates and trips to OPEN to prevent cascaded outages."""

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state: dict[str, CircuitBreakerState] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}

    def get_state(self, provider: str) -> CircuitBreakerState:
        prov = provider.lower()
        state = self._state.get(prov, CircuitBreakerState.CLOSED)
        if state == CircuitBreakerState.OPEN:
            last_fail = self._last_failure_time.get(prov, 0.0)
            if time.monotonic() - last_fail > self.cooldown_seconds:
                self._state[prov] = CircuitBreakerState.HALF_OPEN
                return CircuitBreakerState.HALF_OPEN
        return state

    def record_success(self, provider: str) -> None:
        prov = provider.lower()
        self._consecutive_failures[prov] = 0
        self._state[prov] = CircuitBreakerState.CLOSED

    def record_failure(self, provider: str) -> None:
        prov = provider.lower()
        self._last_failure_time[prov] = time.monotonic()
        failures = self._consecutive_failures.get(prov, 0) + 1
        self._consecutive_failures[prov] = failures

        if failures >= self.failure_threshold:
            self._state[prov] = CircuitBreakerState.OPEN
            logger.warning(
                "Circuit breaker tripped OPEN for provider '%s' after %d consecutive failures.",
                prov,
                failures,
            )

    def is_available(self, provider: str) -> bool:
        return self.get_state(provider) != CircuitBreakerState.OPEN

    def get_open_providers(self) -> set[str]:
        return {p for p in self._state if self.get_state(p) == CircuitBreakerState.OPEN}


class FallbackService:
    """Executes requests across candidate models with bounded retries and graceful fallback."""

    def __init__(
        self,
        provider_registry: ProviderRegistry,
        circuit_breaker: ProviderCircuitBreaker | None = None,
    ) -> None:
        self.providers = provider_registry
        self.circuit_breaker = circuit_breaker or ProviderCircuitBreaker()

    def is_retryable(self, error: Exception) -> bool:
        """Identify transient errors eligible for exponential backoff retries."""
        return isinstance(error, (LLMTimeoutError, LLMRateLimitError, LLMProviderError))

    async def execute_with_fallback(
        self,
        payload: LLMRequestPayload,
        candidates: list[ModelDefinition],
        is_structured: bool = False,
    ) -> LLMResponsePayload:
        """Execute request against candidate sequence, falling back on non-security failures."""
        fallback_history: list[str] = []
        last_error: Exception | None = None

        for idx, candidate in enumerate(candidates):
            provider_name = candidate.provider.lower()

            if not self.circuit_breaker.is_available(provider_name):
                logger.info("Skipping circuit-broken provider '%s'", provider_name)
                continue

            try:
                adapter = self.providers.get_provider(provider_name)
            except Exception as exc:
                fallback_history.append(f"{candidate.provider}/{candidate.model_name}: {exc}")
                continue

            # Clone payload with target model pinned
            candidate_payload = LLMRequestPayload(
                messages=payload.messages,
                task_type=payload.task_type,
                required_capabilities=payload.required_capabilities,
                routing_strategy=payload.routing_strategy,
                data_sensitivity=payload.data_sensitivity,
                pinned_model=candidate.model_name,
                pinned_provider=candidate.provider,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                stop_sequences=payload.stop_sequences,
                prompt_metadata=payload.prompt_metadata,
                idempotency_key=payload.idempotency_key,
                connect_timeout_s=payload.connect_timeout_s,
                request_timeout_s=payload.request_timeout_s,
                total_timeout_s=payload.total_timeout_s,
                structured_request=payload.structured_request,
                metadata=payload.metadata,
            )

            # Bounded retry loop for current candidate (max 2 attempts)
            for attempt in range(2):
                try:
                    if is_structured:
                        response = await adapter.generate_structured(candidate_payload)
                    else:
                        response = await adapter.generate(candidate_payload)

                    # Successful execution
                    self.circuit_breaker.record_success(provider_name)
                    response.fallback_used = idx > 0
                    response.fallback_history = fallback_history
                    return response

                except Exception as exc:
                    last_error = exc
                    # CRITICAL: Do NOT fallback or retry after security or tenant policy violations
                    if isinstance(exc, (SecurityViolationError, TenantPolicyViolationError)):
                        logger.error("Non-recoverable security/policy rejection: %s", exc)
                        raise

                    if self.is_retryable(exc) and attempt == 0:
                        backoff = 0.2 + random.uniform(0.05, 0.15)
                        await asyncio.sleep(backoff)
                        continue

                    # Exhausted attempts on this candidate
                    break

            # Record candidate failure
            self.circuit_breaker.record_failure(provider_name)
            fallback_history.append(f"{candidate.provider}/{candidate.model_name}: {last_error}")

        if last_error:
            if isinstance(last_error, LLMError):
                raise last_error
            raise LLMProviderError(f"All candidate models failed. Last error: {last_error}")

        raise NoHealthyProviderError("No candidate models were available for execution.")
