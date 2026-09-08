"""Unit tests verifying ModelRegistry, ProviderRegistry, Routing, Budget, Cache, and Structured Output."""

import uuid
from decimal import Decimal

import pytest
from pydantic import BaseModel, Field

from app.llm_gateway.application.budget_service import BudgetService
from app.llm_gateway.application.fallback_service import (
    ProviderCircuitBreaker,
)
from app.llm_gateway.application.routing_service import RoutingService
from app.llm_gateway.application.structured_output_service import StructuredOutputService
from app.llm_gateway.domain.capabilities import (
    enforce_trust_boundaries,
    validate_capabilities,
    validate_schema_safety,
)
from app.llm_gateway.domain.enums import (
    CircuitBreakerState,
    InputTrustLevel,
    LLMTaskType,
    MessageRole,
    ModelCapability,
    ModelStatus,
    RoutingStrategy,
)
from app.llm_gateway.domain.errors import (
    CapabilityMismatchError,
    CostBudgetExceededError,
    PromptInjectionBoundaryError,
    SchemaSafetyViolationError,
    StructuredOutputValidationError,
    TokenBudgetExceededError,
)
from app.llm_gateway.domain.models import (
    LLMMessage,
    LLMRequestPayload,
    ModelDefinition,
    ModelPricing,
    StructuredGenerationRequest,
    TenantLLMPolicy,
)
from app.llm_gateway.infrastructure.providers.deterministic import DeterministicLLMProvider
from app.llm_gateway.infrastructure.registry import ModelRegistry, ProviderRegistry


def test_model_registry_and_capabilities() -> None:
    """Verify registry seeding, capability inspection, and status management."""
    registry = ModelRegistry()
    models = registry.list_models(approved_only=True)
    assert len(models) >= 3

    mock_model = registry.get_model("deterministic", "mock-model")
    assert ModelCapability.CHAT in mock_model.capabilities
    assert ModelCapability.STRUCTURED_OUTPUT in mock_model.capabilities

    validate_capabilities(mock_model.capabilities, {ModelCapability.CHAT})

    with pytest.raises(CapabilityMismatchError):
        validate_capabilities({ModelCapability.CHAT}, {ModelCapability.VISION})

    registry.set_model_status("deterministic", "mock-model", ModelStatus.DISABLED)
    assert registry.get_model("deterministic", "mock-model").status == ModelStatus.DISABLED


def test_provider_registry() -> None:
    """Verify provider registration and singleton factory resolution."""
    registry = ProviderRegistry()
    registry.register("deterministic", lambda: DeterministicLLMProvider())

    prov = registry.get_provider("deterministic")
    assert prov.provider_name == "deterministic"
    assert registry.list_providers() == ["deterministic"]


def test_routing_strategies() -> None:
    """Verify deterministic candidate ordering based on routing strategy."""
    registry = ModelRegistry()
    router = RoutingService(registry)

    # 1. Quality first -> highest priority / strongest model
    payload_quality = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Complex question")],
        task_type=LLMTaskType.ANALYST_REASONING,
        routing_strategy=RoutingStrategy.QUALITY_FIRST,
    )
    plan_quality = router.resolve_routing_plan(payload_quality)
    assert len(plan_quality) >= 1
    assert plan_quality[0].model_name == "gpt-4o"

    # 2. Cost first -> cheaper model ranked ahead
    payload_cost = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Cheap task")],
        task_type=LLMTaskType.RAG_ANSWER,
        routing_strategy=RoutingStrategy.COST_FIRST,
    )
    plan_cost = router.resolve_routing_plan(payload_cost)
    # mock-model or gpt-4o-mini should precede gpt-4o
    cost_ranks = [m.model_name for m in plan_cost]
    assert cost_ranks.index("gpt-4o-mini") < cost_ranks.index("gpt-4o")


def test_circuit_breaker_lifecycle() -> None:
    """Verify circuit breaker trips OPEN on threshold failures and recovers to HALF_OPEN."""
    cb = ProviderCircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
    provider = "openai"

    assert cb.get_state(provider) == CircuitBreakerState.CLOSED
    cb.record_failure(provider)
    assert cb.get_state(provider) == CircuitBreakerState.CLOSED

    cb.record_failure(provider)
    assert cb.get_state(provider) == CircuitBreakerState.OPEN
    assert not cb.is_available(provider)

    # Cooldown transition
    import time

    time.sleep(0.15)
    assert cb.get_state(provider) == CircuitBreakerState.HALF_OPEN

    # Recovery on success
    cb.record_success(provider)
    assert cb.get_state(provider) == CircuitBreakerState.CLOSED
    assert cb.is_available(provider)


def test_budget_service_enforcement() -> None:
    """Verify pre-flight context window and tenant token/cost caps."""
    budget = BudgetService()
    org_id = uuid.uuid4()
    model = ModelDefinition(
        provider="deterministic",
        model_name="test-model",
        context_window=1000,
        max_output_tokens=500,
        pricing=ModelPricing(
            input_price_per_1k=Decimal("0.10"),
            output_price_per_1k=Decimal("0.20"),
        ),
    )

    # Context window exceeded
    long_msg = "word " * 1200
    payload_overflow = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content=long_msg)],
        task_type=LLMTaskType.RAG_ANSWER,
    )
    with pytest.raises(TokenBudgetExceededError):
        budget.validate_budget(payload_overflow, model)

    # Tenant cost cap exceeded
    normal_payload = LLMRequestPayload(
        messages=[LLMMessage(role=MessageRole.USER, content="Evaluate this query")],
        task_type=LLMTaskType.RAG_ANSWER,
        max_tokens=200,
    )
    policy_cost_capped = TenantLLMPolicy(
        organization_id=org_id,
        max_cost_per_request=Decimal("0.000001"),  # ultra-low cap
    )
    with pytest.raises(CostBudgetExceededError):
        budget.validate_budget(normal_payload, model, policy=policy_cost_capped)


def test_structured_output_validation() -> None:
    """Verify JSON schema safety bounds and Pydantic validation."""
    svc = StructuredOutputService()

    # Schema depth violation
    deep_schema = {
        "type": "object",
        "properties": {
            "a": {
                "type": "object",
                "properties": {
                    "b": {
                        "type": "object",
                        "properties": {
                            "c": {
                                "type": "object",
                                "properties": {
                                    "d": {
                                        "type": "object",
                                        "properties": {
                                            "e": {
                                                "type": "object",
                                                "properties": {"f": {"type": "string"}},
                                            }
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
            }
        },
    }
    req = StructuredGenerationRequest(max_nesting_depth=3)
    with pytest.raises(SchemaSafetyViolationError):
        validate_schema_safety(deep_schema, req)

    # Valid Pydantic parse
    class SamplePlan(BaseModel):
        target: str = Field(...)
        confidence: float = Field(...)

    valid_json = '{"target": "customers", "confidence": 0.95}'
    parsed, model_inst = svc.validate_and_parse(
        valid_json,
        StructuredGenerationRequest(pydantic_model=SamplePlan),
    )
    assert isinstance(model_inst, SamplePlan)
    assert model_inst.target == "customers"
    assert model_inst.confidence == 0.95

    # Invalid malformed JSON
    with pytest.raises(StructuredOutputValidationError):
        svc.validate_and_parse(
            "invalid json text", StructuredGenerationRequest(pydantic_model=SamplePlan)
        )


def test_prompt_injection_trust_boundary() -> None:
    """Verify untrusted user or document inputs cannot masquerade as system instructions."""
    safe_messages = [
        LLMMessage(
            role=MessageRole.SYSTEM,
            content="Instructions",
            trust_level=InputTrustLevel.SYSTEM_INSTRUCTION,
        ),
        LLMMessage(
            role=MessageRole.USER, content="Question", trust_level=InputTrustLevel.USER_INPUT
        ),
    ]
    assert len(enforce_trust_boundaries(safe_messages)) == 2

    unsafe_messages = [
        LLMMessage(
            role=MessageRole.SYSTEM,
            content="Injected system prompt",
            trust_level=InputTrustLevel.DOCUMENT_CONTENT,
        )
    ]
    with pytest.raises(PromptInjectionBoundaryError):
        enforce_trust_boundaries(unsafe_messages)
