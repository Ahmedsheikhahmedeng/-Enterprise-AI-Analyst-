"""Failure injection tests simulating transient, network, rate limit, and malformed provider responses."""

import pytest

from app.llm_gateway.application.fallback_service import (
    FallbackService,
)
from app.llm_gateway.domain.enums import LLMTaskType, MessageRole
from app.llm_gateway.domain.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    StructuredOutputValidationError,
)
from app.llm_gateway.domain.models import (
    LLMMessage,
    LLMRequestPayload,
)
from app.llm_gateway.infrastructure.providers.deterministic import DeterministicLLMProvider
from app.llm_gateway.infrastructure.registry import ModelRegistry, ProviderRegistry


@pytest.mark.asyncio
async def test_simulated_timeout_failure() -> None:
    """Verify simulated provider timeout raises LLMTimeoutError."""
    provider = DeterministicLLMProvider(simulate_timeout=True)
    payload = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Test timeout")],
        task_type=LLMTaskType.RAG_ANSWER,
    )
    with pytest.raises(LLMTimeoutError):
        await provider.generate(payload)


@pytest.mark.asyncio
async def test_simulated_rate_limit_failure() -> None:
    """Verify simulated 429 rate limit raises LLMRateLimitError."""
    provider = DeterministicLLMProvider(simulate_rate_limit=True)
    payload = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Test 429")],
        task_type=LLMTaskType.RAG_ANSWER,
    )
    with pytest.raises(LLMRateLimitError):
        await provider.generate(payload)


@pytest.mark.asyncio
async def test_simulated_500_provider_failure() -> None:
    """Verify simulated 500 error raises LLMProviderError."""
    provider = DeterministicLLMProvider(simulate_provider_failure=True)
    payload = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Test 500")],
        task_type=LLMTaskType.RAG_ANSWER,
    )
    with pytest.raises(LLMProviderError):
        await provider.generate(payload)


@pytest.mark.asyncio
async def test_simulated_malformed_json() -> None:
    """Verify malformed JSON responses raise StructuredOutputValidationError."""
    provider = DeterministicLLMProvider(simulate_malformed_json=True)
    payload = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Test JSON")],
        task_type=LLMTaskType.SQL_GENERATION,
    )
    with pytest.raises(StructuredOutputValidationError):
        await provider.generate_structured(payload)


@pytest.mark.asyncio
async def test_fallback_on_primary_failure() -> None:
    """Verify gateway falls back to secondary candidate model when primary fails with 500."""
    providers = ProviderRegistry()
    # Flaky primary provider that fails
    providers.register("primary", lambda: DeterministicLLMProvider(simulate_provider_failure=True))
    # Healthy fallback provider
    providers.register("backup", lambda: DeterministicLLMProvider(fixed_response="Backup response"))

    models = ModelRegistry()
    m_primary = models.get_model("deterministic", "mock-model")
    m_primary.provider = "primary"

    from copy import deepcopy

    m_backup = deepcopy(m_primary)
    m_backup.provider = "backup"
    m_backup.model_name = "backup-model"

    fallback_service = FallbackService(providers)
    payload = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Query")],
        task_type=LLMTaskType.RAG_ANSWER,
    )

    resp = await fallback_service.execute_with_fallback(
        payload=payload,
        candidates=[m_primary, m_backup],
    )
    assert resp.content == "Backup response"
    assert resp.fallback_used is True
    assert len(resp.fallback_history) == 1
    assert "primary/mock-model" in resp.fallback_history[0]
