"""Enterprise LLM Gateway Service orchestrating routing, budgeting, fallback, and usage accounting."""

import logging
import time
from collections.abc import AsyncIterator
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm_gateway.application.budget_service import BudgetService
from app.llm_gateway.application.cache_service import CacheService
from app.llm_gateway.application.fallback_service import FallbackService
from app.llm_gateway.application.policy_service import PolicyService
from app.llm_gateway.application.routing_service import RoutingService
from app.llm_gateway.application.structured_output_service import StructuredOutputService
from app.llm_gateway.domain.capabilities import enforce_trust_boundaries
from app.llm_gateway.domain.errors import (
    LLMBudgetError,
)
from app.llm_gateway.domain.models import (
    LLMRequestPayload,
    LLMResponsePayload,
    LLMStreamChunk,
    ProviderHealthStatus,
    StructuredGenerationRequest,
    TenantLLMPolicy,
)
from app.llm_gateway.infrastructure.providers.deterministic import DeterministicLLMProvider
from app.llm_gateway.infrastructure.providers.openai import OpenAIProvider
from app.llm_gateway.infrastructure.registry import ModelRegistry, ProviderRegistry
from app.models.usage import LLMRequest
from app.observability.instrumentation.llm_gateway import (
    LLMInstrumentation,
)
from app.tenancy.context import TenantContext

logger = logging.getLogger(__name__)


class LLMGatewayService:
    """Central gateway facade managing all enterprise AI model invocations."""

    def __init__(
        self,
        provider_registry: ProviderRegistry | None = None,
        model_registry: ModelRegistry | None = None,
        policy_service: PolicyService | None = None,
        budget_service: BudgetService | None = None,
        routing_service: RoutingService | None = None,
        fallback_service: FallbackService | None = None,
        structured_output_service: StructuredOutputService | None = None,
        cache_service: CacheService | None = None,
        instrumentation: LLMInstrumentation | None = None,
    ) -> None:
        # 1. Registries
        self.providers = provider_registry or ProviderRegistry()
        self.models = model_registry or ModelRegistry()
        self._ensure_default_providers()

        # 2. Sub-services
        self.policy_service = policy_service or PolicyService()
        self.budget_service = budget_service or BudgetService()
        self.routing_service = routing_service or RoutingService(self.models)
        self.fallback_service = fallback_service or FallbackService(self.providers)
        self.structured_service = structured_output_service or StructuredOutputService()
        self.cache_service = cache_service or CacheService()
        self.instrumentation = instrumentation or LLMInstrumentation()

    def _ensure_default_providers(self) -> None:
        """Ensure standard providers are registered."""
        prov_list = self.providers.list_providers()
        if "deterministic" not in prov_list:
            self.providers.register("deterministic", lambda: DeterministicLLMProvider())
        if "openai" not in prov_list:
            self.providers.register("openai", lambda: OpenAIProvider())

    async def _persist_usage_record(
        self,
        session: AsyncSession | None,
        tenant_context: TenantContext | None,
        response: LLMResponsePayload,
        task_type: str,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """Persist invocation ledger entry in PostgreSQL llm_requests table."""
        if session is None or tenant_context is None:
            return

        try:
            entry = LLMRequest(
                organization_id=tenant_context.organization_id,
                user_id=tenant_context.user_id,
                provider=response.provider,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                estimated_cost=response.estimated_cost,
                latency_ms=response.latency_ms,
                status="success",
                task_type=task_type,
                fallback_used=response.fallback_used,
                cache_hit=response.cache_hit,
                trace_id=trace_id,
                span_id=span_id,
                metadata_={
                    "fallback_history": response.fallback_history,
                    "finish_reason": response.finish_reason,
                    "request_id": response.request_id,
                },
            )
            session.add(entry)
            await session.flush()
        except Exception as exc:
            logger.warning("Failed to persist LLMRequest ledger entry: %s", exc)

    async def generate(
        self,
        payload: LLMRequestPayload,
        tenant_context: TenantContext | None = None,
        session: AsyncSession | None = None,
        agent_budget_remaining: int | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> LLMResponsePayload:
        """Execute chat completion through policy, routing, budget, and fallback pipeline."""
        start_time = time.monotonic()
        org_id = (
            tenant_context.organization_id
            if tenant_context
            else UUID("00000000-0000-0000-0000-000000000000")
        )

        # 1. Enforce input trust boundaries (anti-injection)
        payload.messages = enforce_trust_boundaries(payload.messages)

        # 2. Retrieve Tenant Policy
        policy: TenantLLMPolicy | None = None
        if session and tenant_context:
            policy = await self.policy_service.get_tenant_policy(
                session, tenant_context.organization_id
            )

        # 3. Check Response Cache
        cache_key: str | None = None
        if self.cache_service.is_cacheable(payload, policy):
            cache_key = self.cache_service.build_key(
                organization_id=org_id,
                model_name=payload.pinned_model or "auto",
                payload=payload,
            )
            cached = await self.cache_service.get_cached_response(cache_key)
            if cached:
                cached.latency_ms = int((time.monotonic() - start_time) * 1000)
                self.instrumentation.record_request(
                    provider=cached.provider,
                    model=cached.model,
                    task_type=payload.task_type.value,
                    status="success",
                    duration_s=time.monotonic() - start_time,
                    input_tokens=cached.input_tokens,
                    output_tokens=cached.output_tokens,
                    estimated_cost=float(cached.estimated_cost),
                    cache_hit=True,
                )
                await self._persist_usage_record(
                    session=session,
                    tenant_context=tenant_context,
                    response=cached,
                    task_type=payload.task_type.value,
                    trace_id=trace_id,
                    span_id=span_id,
                )
                return cached

        # 4. Resolve Candidate Models via Routing
        open_circuits = self.fallback_service.circuit_breaker.get_open_providers()
        candidates = self.routing_service.resolve_routing_plan(
            payload=payload,
            policy=policy,
            open_circuit_providers=open_circuits,
        )

        # 5. Pre-flight Budget Validation on Primary Candidate
        primary_candidate = candidates[0]
        try:
            self.budget_service.validate_budget(
                payload=payload,
                model=primary_candidate,
                policy=policy,
                agent_budget_remaining=agent_budget_remaining,
            )
        except LLMBudgetError:
            self.instrumentation.record_budget_rejection(payload.task_type.value, "budget_exceeded")
            raise

        # 6. Execution with Fallback
        try:
            response = await self.fallback_service.execute_with_fallback(
                payload=payload,
                candidates=candidates,
                is_structured=False,
            )
        except Exception:
            duration_s = time.monotonic() - start_time
            self.instrumentation.record_request(
                provider=primary_candidate.provider,
                model=primary_candidate.model_name,
                task_type=payload.task_type.value,
                status="failed",
                duration_s=duration_s,
            )
            raise

        duration_s = time.monotonic() - start_time
        # Compute exact cost from chosen model pricing
        try:
            chosen_def = self.models.get_model(response.provider, response.model)
            response.estimated_cost = chosen_def.pricing.calculate_cost(
                response.input_tokens, response.output_tokens
            )
        except Exception:
            response.estimated_cost = primary_candidate.pricing.calculate_cost(
                response.input_tokens, response.output_tokens
            )

        # 7. Record Observability Telemetry
        self.instrumentation.record_request(
            provider=response.provider,
            model=response.model,
            task_type=payload.task_type.value,
            status="success",
            duration_s=duration_s,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=float(response.estimated_cost),
            fallback_used=response.fallback_used,
            cache_hit=False,
        )

        # 8. Persist Usage Ledger Record
        await self._persist_usage_record(
            session=session,
            tenant_context=tenant_context,
            response=response,
            task_type=payload.task_type.value,
            trace_id=trace_id,
            span_id=span_id,
        )

        # 9. Store in Cache if Eligible
        if cache_key and self.cache_service.is_cacheable(payload, policy):
            await self.cache_service.store_response(cache_key, response)

        return response

    async def generate_structured(
        self,
        payload: LLMRequestPayload,
        structured_req: StructuredGenerationRequest,
        tenant_context: TenantContext | None = None,
        session: AsyncSession | None = None,
        agent_budget_remaining: int | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> tuple[LLMResponsePayload, BaseModel | None]:
        """Execute structured JSON generation, parsing, and Pydantic validation."""
        payload.structured_request = structured_req
        start_time = time.monotonic()
        org_id = (
            tenant_context.organization_id
            if tenant_context
            else UUID("00000000-0000-0000-0000-000000000000")
        )

        payload.messages = enforce_trust_boundaries(payload.messages)

        policy: TenantLLMPolicy | None = None
        if session and tenant_context:
            policy = await self.policy_service.get_tenant_policy(
                session, tenant_context.organization_id
            )

        # Check Cache
        cache_key: str | None = None
        if self.cache_service.is_cacheable(payload, policy):
            cache_key = self.cache_service.build_key(
                organization_id=org_id,
                model_name=payload.pinned_model or "auto",
                payload=payload,
            )
            cached = await self.cache_service.get_cached_response(cache_key)
            if cached and cached.content:
                parsed, pydantic_inst = self.structured_service.validate_and_parse(
                    cached.content, structured_req
                )
                cached.parsed_json = parsed
                cached.latency_ms = int((time.monotonic() - start_time) * 1000)
                self.instrumentation.record_request(
                    provider=cached.provider,
                    model=cached.model,
                    task_type=payload.task_type.value,
                    status="success",
                    duration_s=time.monotonic() - start_time,
                    input_tokens=cached.input_tokens,
                    output_tokens=cached.output_tokens,
                    estimated_cost=float(cached.estimated_cost),
                    cache_hit=True,
                )
                await self._persist_usage_record(
                    session=session,
                    tenant_context=tenant_context,
                    response=cached,
                    task_type=payload.task_type.value,
                    trace_id=trace_id,
                    span_id=span_id,
                )
                return cached, pydantic_inst

        # Resolve Candidates
        open_circuits = self.fallback_service.circuit_breaker.get_open_providers()
        candidates = self.routing_service.resolve_routing_plan(
            payload=payload,
            policy=policy,
            open_circuit_providers=open_circuits,
        )

        primary_candidate = candidates[0]
        self.budget_service.validate_budget(
            payload=payload,
            model=primary_candidate,
            policy=policy,
            agent_budget_remaining=agent_budget_remaining,
        )

        response = await self.fallback_service.execute_with_fallback(
            payload=payload,
            candidates=candidates,
            is_structured=True,
        )

        # Parse & Validate Structured Output
        parsed, pydantic_inst = self.structured_service.validate_and_parse(
            response.content, structured_req
        )
        response.parsed_json = parsed

        duration_s = time.monotonic() - start_time
        try:
            chosen_def = self.models.get_model(response.provider, response.model)
            response.estimated_cost = chosen_def.pricing.calculate_cost(
                response.input_tokens, response.output_tokens
            )
        except Exception:
            response.estimated_cost = primary_candidate.pricing.calculate_cost(
                response.input_tokens, response.output_tokens
            )

        self.instrumentation.record_request(
            provider=response.provider,
            model=response.model,
            task_type=payload.task_type.value,
            status="success",
            duration_s=duration_s,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=float(response.estimated_cost),
            fallback_used=response.fallback_used,
            cache_hit=False,
        )

        await self._persist_usage_record(
            session=session,
            tenant_context=tenant_context,
            response=response,
            task_type=payload.task_type.value,
            trace_id=trace_id,
            span_id=span_id,
        )

        if cache_key and self.cache_service.is_cacheable(payload, policy):
            await self.cache_service.store_response(cache_key, response)

        return response, pydantic_inst

    async def generate_stream(
        self,
        payload: LLMRequestPayload,
        tenant_context: TenantContext | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream token chunks asynchronously from selected provider."""
        candidates = self.routing_service.resolve_routing_plan(payload=payload)
        candidate = candidates[0]
        adapter = self.providers.get_provider(candidate.provider)
        async for chunk in adapter.generate_stream(payload):
            yield chunk

    async def health_check(self, provider_name: str | None = None) -> list[ProviderHealthStatus]:
        """Perform non-invasive health checks on registered providers."""
        targets = [provider_name] if provider_name else self.providers.list_providers()
        statuses: list[ProviderHealthStatus] = []
        for prov in targets:
            try:
                adapter = self.providers.get_provider(prov)
                stat = await adapter.health_check()
                statuses.append(stat)
            except Exception as exc:
                statuses.append(
                    ProviderHealthStatus(
                        provider=prov,
                        is_healthy=False,
                        latency_ms=0,
                        failure_rate=1.0,
                        circuit_state=self.fallback_service.circuit_breaker.get_state(prov),
                        message=str(exc),
                    )
                )
        return statuses


# Global singleton instance for platform-wide dependency injection
_global_gateway_service: LLMGatewayService | None = None


def get_llm_gateway_service() -> LLMGatewayService:
    """Retrieve singleton accessor for LLMGatewayService."""
    global _global_gateway_service
    if _global_gateway_service is None:
        _global_gateway_service = LLMGatewayService()
    return _global_gateway_service
