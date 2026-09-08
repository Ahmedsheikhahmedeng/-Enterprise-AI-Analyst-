"""FastAPI REST API router for Enterprise FinOps, AI Cost Governance & Usage Optimization."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.postgres import get_db_session
from app.finops.allocation import CostAllocationEngine
from app.finops.models import Budget, CostPolicy, ModelPricing, Quota
from app.finops.schemas import (
    AttributionBreakdownItem,
    BudgetCreate,
    BudgetResponse,
    CostAnomalyResponse,
    CostEventResponse,
    CostForecastResponse,
    CostPolicyCreate,
    CostPolicyResponse,
    FinOpsOverviewResponse,
    FinOpsReadinessResponse,
    ModelPricingCreate,
    ModelPricingResponse,
    OptimizationRecommendationResponse,
    QuotaCreate,
    QuotaResponse,
)
from app.finops.service import FinOpsService
from app.models.user import User
from app.rbac.dependencies import require_permission
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/finops", tags=["Enterprise FinOps & Cost Governance"])


# ---------------------------------------------------------------------------
# Overview & Readiness
# ---------------------------------------------------------------------------
@router.get(
    "/overview",
    response_model=FinOpsOverviewResponse,
    summary="Get unified FinOps spend KPIs, budget state, and disclaimer",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def get_finops_overview(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FinOpsOverviewResponse:
    service = FinOpsService(db)
    return await service.get_overview(organization_id=tenant.organization_id)


@router.get(
    "/readiness",
    response_model=FinOpsReadinessResponse,
    summary="Get FinOps release safety readiness determination and blockers",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def get_finops_readiness(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FinOpsReadinessResponse:
    service = FinOpsService(db)
    return await service.get_readiness(organization_id=tenant.organization_id)


# ---------------------------------------------------------------------------
# Usage & Ledger
# ---------------------------------------------------------------------------
@router.get(
    "/usage",
    response_model=list[CostEventResponse],
    summary="List immutable cost ledger usage records",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def list_usage_events(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
) -> list[CostEventResponse]:
    service = FinOpsService(db)
    events = await service.repo.list_events(organization_id=tenant.organization_id, limit=limit)
    return [CostEventResponse.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# Multi-Dimensional Cost Breakdowns
# ---------------------------------------------------------------------------
@router.get(
    "/costs/by-model",
    response_model=list[AttributionBreakdownItem],
    summary="Aggregate spend and token metrics grouped by model",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def get_costs_by_model(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AttributionBreakdownItem]:
    service = FinOpsService(db)
    events = await service.repo.list_events(organization_id=tenant.organization_id, limit=5000)
    return CostAllocationEngine.aggregate_by_dimension(events, "model")


@router.get(
    "/costs/by-provider",
    response_model=list[AttributionBreakdownItem],
    summary="Aggregate spend and request metrics grouped by provider",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def get_costs_by_provider(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AttributionBreakdownItem]:
    service = FinOpsService(db)
    events = await service.repo.list_events(organization_id=tenant.organization_id, limit=5000)
    return CostAllocationEngine.aggregate_by_dimension(events, "provider")


@router.get(
    "/costs/by-feature",
    response_model=list[AttributionBreakdownItem],
    summary="Aggregate spend and tokens grouped by feature operation (RAG, SQL, Agent)",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def get_costs_by_feature(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AttributionBreakdownItem]:
    service = FinOpsService(db)
    events = await service.repo.list_events(organization_id=tenant.organization_id, limit=5000)
    return CostAllocationEngine.aggregate_by_dimension(events, "operation")


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------
@router.get(
    "/budgets",
    response_model=list[BudgetResponse],
    summary="List organization budgets with real-time consumption and state",
    dependencies=[Depends(require_permission("finops.budget.read"))],
)
async def list_budgets(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[BudgetResponse]:
    service = FinOpsService(db)
    return await service.get_budgets_with_consumption(tenant.organization_id)


@router.post(
    "/budgets",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hierarchical budget allocation",
    dependencies=[Depends(require_permission("finops.budget.manage"))],
)
async def create_budget(
    payload: BudgetCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> BudgetResponse:
    service = FinOpsService(db)
    budget = Budget(
        id=f"bgt-{uuid.uuid4().hex[:16]}",
        organization_id=tenant.organization_id,
        scope=payload.scope.value,
        scope_id=payload.scope_id,
        parent_budget_id=payload.parent_budget_id,
        period=payload.period.value,
        limit_amount=payload.limit_amount,
        currency=payload.currency,
        warning_percent=payload.warning_percent,
        critical_percent=payload.critical_percent,
        enabled=True,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        created_by=user.email,
    )
    saved = await service.repo.save_budget(budget)
    res = await service.get_budgets_with_consumption(tenant.organization_id)
    return next((b for b in res if b.id == saved.id), BudgetResponse.model_validate(saved))


# ---------------------------------------------------------------------------
# Quotas
# ---------------------------------------------------------------------------
@router.get(
    "/quotas",
    response_model=list[QuotaResponse],
    summary="List organization consumption quotas and live utilization",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def list_quotas(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[QuotaResponse]:
    service = FinOpsService(db)
    return await service.get_quotas_with_usage(tenant.organization_id)


@router.post(
    "/quotas",
    response_model=QuotaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update resource consumption quota",
    dependencies=[Depends(require_permission("finops.quota.manage"))],
)
async def create_quota(
    payload: QuotaCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> QuotaResponse:
    service = FinOpsService(db)
    quota = Quota(
        id=f"qta-{uuid.uuid4().hex[:16]}",
        organization_id=tenant.organization_id,
        quota_type=payload.quota_type.value,
        scope=payload.scope,
        scope_id=payload.scope_id,
        limit_value=payload.limit_value,
        period_seconds=payload.period_seconds,
        enforcement_mode=payload.enforcement_mode.value,
        enabled=True,
    )
    saved = await service.repo.save_quota(quota)
    return QuotaResponse.model_validate(saved)


# ---------------------------------------------------------------------------
# Anomalies, Forecasts & Recommendations
# ---------------------------------------------------------------------------
@router.get(
    "/anomalies",
    response_model=list[CostAnomalyResponse],
    summary="List detected cost and token volume spikes",
    dependencies=[Depends(require_permission("finops.anomaly.read"))],
)
async def list_anomalies(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[CostAnomalyResponse]:
    service = FinOpsService(db)
    anomalies = await service.repo.list_anomalies(tenant.organization_id, status=status_filter)
    return [CostAnomalyResponse.model_validate(a) for a in anomalies]


@router.get(
    "/forecasts",
    response_model=list[CostForecastResponse],
    summary="List spend trajectory forecasts and budget overruns",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def list_forecasts(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CostForecastResponse]:
    service = FinOpsService(db)
    forecasts = await service.repo.list_forecasts(tenant.organization_id)
    return [CostForecastResponse.model_validate(f) for f in forecasts]


@router.get(
    "/recommendations",
    response_model=list[OptimizationRecommendationResponse],
    summary="List actionable AI cost optimization recommendations",
    dependencies=[Depends(require_permission("finops.optimization.read"))],
)
async def list_recommendations(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[OptimizationRecommendationResponse]:
    service = FinOpsService(db)
    recs = await service.repo.list_recommendations(tenant.organization_id)
    return [OptimizationRecommendationResponse.model_validate(r) for r in recs]


# ---------------------------------------------------------------------------
# Pricing Registry
# ---------------------------------------------------------------------------
@router.get(
    "/pricing",
    response_model=list[ModelPricingResponse],
    summary="List active versioned model pricing rates",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def list_pricing(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    provider: str | None = None,
) -> list[ModelPricingResponse]:
    service = FinOpsService(db)
    pricing = await service.repo.list_pricing(provider=provider)
    return [ModelPricingResponse.model_validate(p) for p in pricing]


@router.post(
    "/pricing",
    response_model=ModelPricingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new versioned model pricing rate",
    dependencies=[Depends(require_permission("finops.pricing.manage"))],
)
async def create_pricing(
    payload: ModelPricingCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ModelPricingResponse:
    service = FinOpsService(db)
    existing = await service.repo.list_pricing(provider=payload.provider)
    matching = [p for p in existing if p.model.lower() == payload.model.lower()]
    new_version = (max((p.version for p in matching), default=0)) + 1

    pricing = ModelPricing(
        id=f"prc-{uuid.uuid4().hex[:16]}",
        provider=payload.provider,
        model=payload.model,
        version=new_version,
        input_price_per_1m=payload.input_price_per_1m,
        output_price_per_1m=payload.output_price_per_1m,
        cached_input_price_per_1m=payload.cached_input_price_per_1m,
        currency=payload.currency,
        effective_from=payload.effective_from,
        effective_until=payload.effective_until,
        source=payload.source,
        is_active=True,
    )
    saved = await service.repo.save_pricing(pricing)
    return ModelPricingResponse.model_validate(saved)


# ---------------------------------------------------------------------------
# Cost Policies
# ---------------------------------------------------------------------------
@router.get(
    "/policies",
    response_model=list[CostPolicyResponse],
    summary="List organization cost governance policies",
    dependencies=[Depends(require_permission("finops.read"))],
)
async def list_policies(
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[CostPolicyResponse]:
    service = FinOpsService(db)
    policies = await service.repo.list_policies(tenant.organization_id)
    return [CostPolicyResponse.model_validate(p) for p in policies]


@router.post(
    "/policies",
    response_model=CostPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update cost governance policy",
    dependencies=[Depends(require_permission("finops.policy.manage"))],
)
async def create_policy(
    payload: CostPolicyCreate,
    tenant: Annotated[TenantContext, Depends(get_tenant_context)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> CostPolicyResponse:
    service = FinOpsService(db)
    policy = CostPolicy(
        id=f"pol-{uuid.uuid4().hex[:16]}",
        organization_id=tenant.organization_id,
        name=payload.name,
        max_cost_per_request=payload.max_cost_per_request,
        max_cost_per_day=payload.max_cost_per_day,
        max_tokens_per_request=payload.max_tokens_per_request,
        max_tokens_per_day=payload.max_tokens_per_day,
        max_llm_calls_per_run=payload.max_llm_calls_per_run,
        enforcement_mode=payload.enforcement_mode.value,
        enabled=True,
    )
    saved = await service.repo.save_policy(policy)
    return CostPolicyResponse.model_validate(saved)
