"""FastAPI REST routes for Enterprise LLM Gateway administration and usage telemetry."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_db_session
from app.llm_gateway.api.schemas import (
    LLMUsageRecordResponse,
    ModelDefinitionResponse,
    ProviderHealthResponse,
    TenantLLMPolicyResponse,
    UpdateTenantLLMPolicyRequest,
)
from app.llm_gateway.application.gateway_service import (
    LLMGatewayService,
    get_llm_gateway_service,
)
from app.llm_gateway.domain.enums import ModelCapability, ModelStatus
from app.models.usage import LLMRequest
from app.rbac.catalog import (
    PERM_LLM_POLICY_READ,
    PERM_LLM_POLICY_UPDATE,
    PERM_LLM_READ,
    PERM_LLM_USAGE_READ,
)
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/llm", tags=["LLM Gateway & Provider Management"])


@router.get(
    "/models",
    response_model=list[ModelDefinitionResponse],
    dependencies=[Depends(require_permission(PERM_LLM_READ))],
)
async def list_models(
    provider: str | None = None,
    status_filter: str | None = None,
    gateway: Annotated[LLMGatewayService, Depends(get_llm_gateway_service)] = None,  # type: ignore[assignment]
) -> list[ModelDefinitionResponse]:
    """List approved models available for enterprise routing."""
    st = (
        ModelStatus(status_filter)
        if status_filter and status_filter in ModelStatus._value2member_map_
        else None
    )
    models = gateway.models.list_models(provider=provider, status=st, approved_only=True)
    return [
        ModelDefinitionResponse(
            provider=m.provider,
            model_name=m.model_name,
            model_version=m.model_version,
            status=m.status,
            is_approved=m.is_approved,
            capabilities=[c.value for c in m.capabilities],
            input_price_per_1k=m.pricing.input_price_per_1k,
            output_price_per_1k=m.pricing.output_price_per_1k,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            priority=m.priority,
            metadata=m.metadata,
        )
        for m in models
    ]


@router.get(
    "/providers",
    response_model=list[str],
    dependencies=[Depends(require_permission(PERM_LLM_READ))],
)
async def list_providers(
    gateway: Annotated[LLMGatewayService, Depends(get_llm_gateway_service)] = None,  # type: ignore[assignment]
) -> list[str]:
    """List all registered AI model provider adapters."""
    return gateway.providers.list_providers()


@router.get(
    "/health",
    response_model=list[ProviderHealthResponse],
    dependencies=[Depends(require_permission(PERM_LLM_READ))],
)
async def get_provider_health(
    provider: str | None = None,
    gateway: Annotated[LLMGatewayService, Depends(get_llm_gateway_service)] = None,  # type: ignore[assignment]
) -> list[ProviderHealthResponse]:
    """Inspect operational health and latency of LLM providers."""
    statuses = await gateway.health_check(provider_name=provider)
    return [
        ProviderHealthResponse(
            provider=s.provider,
            is_healthy=s.is_healthy,
            latency_ms=s.latency_ms,
            failure_rate=s.failure_rate,
            circuit_state=s.circuit_state,
            message=s.message,
        )
        for s in statuses
    ]


@router.get(
    "/policies",
    response_model=TenantLLMPolicyResponse,
    dependencies=[Depends(require_permission(PERM_LLM_POLICY_READ))],
)
async def get_tenant_policy(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    gateway: Annotated[LLMGatewayService, Depends(get_llm_gateway_service)] = None,  # type: ignore[assignment]
) -> TenantLLMPolicyResponse:
    """Retrieve organization LLM governance policy and budget limits."""
    policy = await gateway.policy_service.get_tenant_policy(session, tenant_context.organization_id)
    return TenantLLMPolicyResponse(
        organization_id=policy.organization_id,
        allowed_providers=policy.allowed_providers,
        allowed_models=policy.allowed_models,
        max_tokens_per_request=policy.max_tokens_per_request,
        max_cost_per_request=policy.max_cost_per_request,
        allowed_capabilities=[c.value for c in policy.allowed_capabilities],
        data_residency=policy.data_residency,
        streaming_allowed=policy.streaming_allowed,
        caching_allowed=policy.caching_allowed,
        metadata=policy.metadata,
    )


@router.patch(
    "/policies",
    response_model=TenantLLMPolicyResponse,
    dependencies=[Depends(require_permission(PERM_LLM_POLICY_UPDATE))],
)
async def update_tenant_policy(
    body: UpdateTenantLLMPolicyRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    gateway: Annotated[LLMGatewayService, Depends(get_llm_gateway_service)] = None,  # type: ignore[assignment]
) -> TenantLLMPolicyResponse:
    """Update organization LLM governance policy."""
    current = await gateway.policy_service.get_tenant_policy(
        session, tenant_context.organization_id
    )

    if body.allowed_providers is not None:
        current.allowed_providers = body.allowed_providers
    if body.allowed_models is not None:
        current.allowed_models = body.allowed_models
    if body.max_tokens_per_request is not None:
        current.max_tokens_per_request = body.max_tokens_per_request
    if body.max_cost_per_request is not None:
        current.max_cost_per_request = body.max_cost_per_request
    if body.allowed_capabilities is not None:
        current.allowed_capabilities = {
            ModelCapability(c)
            for c in body.allowed_capabilities
            if c in ModelCapability._value2member_map_
        }
    if body.data_residency is not None:
        current.data_residency = body.data_residency
    if body.streaming_allowed is not None:
        current.streaming_allowed = body.streaming_allowed
    if body.caching_allowed is not None:
        current.caching_allowed = body.caching_allowed
    if body.metadata is not None:
        current.metadata = body.metadata

    updated = await gateway.policy_service.upsert_tenant_policy(session, current)
    return TenantLLMPolicyResponse(
        organization_id=updated.organization_id,
        allowed_providers=updated.allowed_providers,
        allowed_models=updated.allowed_models,
        max_tokens_per_request=updated.max_tokens_per_request,
        max_cost_per_request=updated.max_cost_per_request,
        allowed_capabilities=[c.value for c in updated.allowed_capabilities],
        data_residency=updated.data_residency,
        streaming_allowed=updated.streaming_allowed,
        caching_allowed=updated.caching_allowed,
        metadata=updated.metadata,
    )


@router.get(
    "/usage",
    response_model=list[LLMUsageRecordResponse],
    dependencies=[Depends(require_permission(PERM_LLM_USAGE_READ))],
)
async def list_usage_records(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[LLMUsageRecordResponse]:
    """Retrieve organization metered LLM request ledgers."""
    stmt = (
        select(LLMRequest)
        .where(LLMRequest.organization_id == tenant_context.organization_id)
        .order_by(LLMRequest.created_at.desc())
        .limit(limit)
    )
    res = await session.execute(stmt)
    records = res.scalars().all()

    return [
        LLMUsageRecordResponse(
            id=r.id,
            provider=r.provider,
            model=r.model,
            task_type=r.task_type,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            total_tokens=r.total_tokens,
            estimated_cost=r.estimated_cost,
            latency_ms=r.latency_ms,
            status=r.status,
            fallback_used=r.fallback_used,
            cache_hit=r.cache_hit,
            created_at=r.created_at,
        )
        for r in records
    ]
