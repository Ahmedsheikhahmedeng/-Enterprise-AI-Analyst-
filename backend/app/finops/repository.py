"""Tenant-isolated database repository for all FinOps & AI Cost Governance entities."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.finops.models import (
    Budget,
    CostAnomaly,
    CostCorrection,
    CostEvent,
    CostForecast,
    CostPolicy,
    CostReconciliation,
    ModelPricing,
    OptimizationRecommendation,
    Quota,
)


class FinOpsRepository:
    """Encapsulates tenant-aware database operations across all FinOps tables."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Cost Events (Usage Ledger)
    # -------------------------------------------------------------------------
    async def list_events(
        self,
        organization_id: uuid.UUID | None = None,
        provider: str | None = None,
        model: str | None = None,
        operation: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 1000,
    ) -> list[CostEvent]:
        stmt = select(CostEvent)
        if organization_id:
            stmt = stmt.where(CostEvent.organization_id == organization_id)
        if provider:
            stmt = stmt.where(CostEvent.provider == provider)
        if model:
            stmt = stmt.where(CostEvent.model == model)
        if operation:
            stmt = stmt.where(CostEvent.operation == operation)
        if start_time:
            stmt = stmt.where(CostEvent.timestamp >= start_time)
        if end_time:
            stmt = stmt.where(CostEvent.timestamp <= end_time)

        stmt = stmt.order_by(CostEvent.timestamp.desc()).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_event(self, event: CostEvent) -> CostEvent:
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_event(
        self, event_id: str, organization_id: uuid.UUID | None = None
    ) -> CostEvent | None:
        stmt = select(CostEvent).where(CostEvent.id == event_id)
        if organization_id:
            stmt = stmt.where(CostEvent.organization_id == organization_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Model Pricing
    # -------------------------------------------------------------------------
    async def list_pricing(self, provider: str | None = None) -> list[ModelPricing]:
        stmt = select(ModelPricing).where(ModelPricing.is_active.is_(True))
        if provider:
            stmt = stmt.where(ModelPricing.provider == provider)
        stmt = stmt.order_by(ModelPricing.provider, ModelPricing.model, ModelPricing.version.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_pricing(self, pricing: ModelPricing) -> ModelPricing:
        self.db.add(pricing)
        await self.db.flush()
        return pricing

    async def get_pricing(self, pricing_id: str) -> ModelPricing | None:
        stmt = select(ModelPricing).where(ModelPricing.id == pricing_id)
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    # -------------------------------------------------------------------------
    # Budgets
    # -------------------------------------------------------------------------
    async def list_budgets(self, organization_id: uuid.UUID) -> list[Budget]:
        stmt = (
            select(Budget)
            .where(Budget.organization_id == organization_id)
            .order_by(Budget.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_budget(self, budget_id: str, organization_id: uuid.UUID) -> Budget | None:
        stmt = select(Budget).where(
            Budget.id == budget_id, Budget.organization_id == organization_id
        )
        res = await self.db.execute(stmt)
        return res.scalar_one_or_none()

    async def save_budget(self, budget: Budget) -> Budget:
        self.db.add(budget)
        await self.db.flush()
        return budget

    # -------------------------------------------------------------------------
    # Quotas
    # -------------------------------------------------------------------------
    async def list_quotas(self, organization_id: uuid.UUID) -> list[Quota]:
        stmt = (
            select(Quota)
            .where(Quota.organization_id == organization_id)
            .order_by(Quota.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_quota(self, quota: Quota) -> Quota:
        self.db.add(quota)
        await self.db.flush()
        return quota

    # -------------------------------------------------------------------------
    # Cost Policies
    # -------------------------------------------------------------------------
    async def list_policies(self, organization_id: uuid.UUID) -> list[CostPolicy]:
        stmt = (
            select(CostPolicy)
            .where(CostPolicy.organization_id == organization_id)
            .order_by(CostPolicy.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_policy(self, policy: CostPolicy) -> CostPolicy:
        self.db.add(policy)
        await self.db.flush()
        return policy

    # -------------------------------------------------------------------------
    # Anomalies
    # -------------------------------------------------------------------------
    async def list_anomalies(
        self, organization_id: uuid.UUID, status: str | None = None
    ) -> list[CostAnomaly]:
        stmt = select(CostAnomaly).where(CostAnomaly.organization_id == organization_id)
        if status:
            stmt = stmt.where(CostAnomaly.status == status)
        stmt = stmt.order_by(CostAnomaly.detected_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_anomaly(self, anomaly: CostAnomaly) -> CostAnomaly:
        self.db.add(anomaly)
        await self.db.flush()
        return anomaly

    # -------------------------------------------------------------------------
    # Forecasts
    # -------------------------------------------------------------------------
    async def list_forecasts(self, organization_id: uuid.UUID) -> list[CostForecast]:
        stmt = (
            select(CostForecast)
            .where(CostForecast.organization_id == organization_id)
            .order_by(CostForecast.created_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_forecast(self, forecast: CostForecast) -> CostForecast:
        self.db.add(forecast)
        await self.db.flush()
        return forecast

    # -------------------------------------------------------------------------
    # Recommendations
    # -------------------------------------------------------------------------
    async def list_recommendations(
        self, organization_id: uuid.UUID, status: str | None = None
    ) -> list[OptimizationRecommendation]:
        stmt = select(OptimizationRecommendation).where(
            OptimizationRecommendation.organization_id == organization_id
        )
        if status:
            stmt = stmt.where(OptimizationRecommendation.status == status)
        stmt = stmt.order_by(OptimizationRecommendation.expected_saving.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_recommendation(
        self, rec: OptimizationRecommendation
    ) -> OptimizationRecommendation:
        self.db.add(rec)
        await self.db.flush()
        return rec

    # -------------------------------------------------------------------------
    # Reconciliations
    # -------------------------------------------------------------------------
    async def list_reconciliations(
        self, organization_id: uuid.UUID | None = None
    ) -> list[CostReconciliation]:
        stmt = select(CostReconciliation)
        if organization_id:
            stmt = stmt.where(CostReconciliation.organization_id == organization_id)
        stmt = stmt.order_by(CostReconciliation.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_reconciliation(self, rec: CostReconciliation) -> CostReconciliation:
        self.db.add(rec)
        await self.db.flush()
        return rec

    # -------------------------------------------------------------------------
    # Corrections
    # -------------------------------------------------------------------------
    async def list_corrections(self, organization_id: uuid.UUID) -> list[CostCorrection]:
        stmt = (
            select(CostCorrection)
            .where(CostCorrection.organization_id == organization_id)
            .order_by(CostCorrection.corrected_at.desc())
        )
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def save_correction(self, correction: CostCorrection) -> CostCorrection:
        self.db.add(correction)
        await self.db.flush()
        return correction
