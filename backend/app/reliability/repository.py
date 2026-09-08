"""Repository for tenant-isolated persistence of Reliability & Chaos records."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.reliability.models import (
    ProductionReadinessRecord,
    ReliabilityAssertion,
    ReliabilityFault,
    ReliabilityRun,
    ReliabilityScenario,
    ReliabilityScorecard,
)


class ReliabilityRepository:
    """Provides isolated, transactional database operations for reliability data."""

    def __init__(self, db: AsyncSession, organization_id: uuid.UUID | None = None) -> None:
        self.db = db
        self.organization_id = organization_id

    # -------------------------------------------------------------------------
    # Scenarios
    # -------------------------------------------------------------------------
    async def create_scenario(
        self,
        *,
        id: str | None = None,
        name: str,
        description: str,
        category: str,
        severity: str = "SEV2",
        enabled: bool = True,
        timeout_seconds: int = 60,
        max_duration_seconds: int = 120,
        parameters: dict[str, Any] | None = None,
    ) -> ReliabilityScenario:
        scenario = ReliabilityScenario(
            id=id or str(uuid.uuid4()),
            organization_id=self.organization_id,
            name=name,
            description=description,
            category=category,
            severity=severity,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            max_duration_seconds=max_duration_seconds,
            parameters=parameters or {},
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.db.add(scenario)
        await self.db.flush()
        await self.db.refresh(scenario)
        return scenario

    async def get_scenario(self, scenario_id: str) -> ReliabilityScenario | None:
        stmt = select(ReliabilityScenario).where(ReliabilityScenario.id == scenario_id)
        if self.organization_id:
            stmt = stmt.where(
                (ReliabilityScenario.organization_id == self.organization_id)
                | (ReliabilityScenario.organization_id.is_(None))
            )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_scenarios(
        self, category: str | None = None, limit: int = 100
    ) -> Sequence[ReliabilityScenario]:
        stmt = select(ReliabilityScenario)
        if self.organization_id:
            stmt = stmt.where(
                (ReliabilityScenario.organization_id == self.organization_id)
                | (ReliabilityScenario.organization_id.is_(None))
            )
        if category:
            stmt = stmt.where(ReliabilityScenario.category == category)
        stmt = stmt.order_by(ReliabilityScenario.created_at.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # -------------------------------------------------------------------------
    # Runs
    # -------------------------------------------------------------------------
    async def create_run(
        self,
        *,
        id: str | None = None,
        scenario_id: str,
        environment: str = "test",
        status: str = "PENDING",
        fault_type: str,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_ms: float | None = None,
        mttd_seconds: float | None = None,
        mtta_seconds: float | None = None,
        mttr_seconds: float | None = None,
        time_to_recovery_seconds: float | None = None,
        slo_impact_pct: float = 0.0,
        error_budget_consumed_pct: float = 0.0,
        alerts_created_count: int = 0,
        incidents_created_count: int = 0,
        release_gate_verdict: str | None = None,
        failure_classification: str | None = None,
        correlation_id: str | None = None,
        actor_id: uuid.UUID | None = None,
        summary: str | None = None,
    ) -> ReliabilityRun:
        run = ReliabilityRun(
            id=id or str(uuid.uuid4()),
            scenario_id=scenario_id,
            organization_id=self.organization_id,
            environment=environment,
            status=status,
            fault_type=fault_type,
            started_at=started_at or datetime.now(UTC),
            finished_at=finished_at,
            duration_ms=duration_ms,
            mttd_seconds=mttd_seconds,
            mtta_seconds=mtta_seconds,
            mttr_seconds=mttr_seconds,
            time_to_recovery_seconds=time_to_recovery_seconds,
            slo_impact_pct=slo_impact_pct,
            error_budget_consumed_pct=error_budget_consumed_pct,
            alerts_created_count=alerts_created_count,
            incidents_created_count=incidents_created_count,
            release_gate_verdict=release_gate_verdict,
            failure_classification=failure_classification,
            correlation_id=correlation_id,
            actor_id=actor_id,
            summary=summary,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.db.add(run)
        await self.db.flush()
        await self.db.refresh(run)
        return run

    async def get_run(self, run_id: str) -> ReliabilityRun | None:
        stmt = (
            select(ReliabilityRun)
            .where(ReliabilityRun.id == run_id)
            .options(
                selectinload(ReliabilityRun.faults),
                selectinload(ReliabilityRun.assertions),
            )
        )
        if self.organization_id:
            stmt = stmt.where(
                (ReliabilityRun.organization_id == self.organization_id)
                | (ReliabilityRun.organization_id.is_(None))
            )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_runs(self, limit: int = 50) -> Sequence[ReliabilityRun]:
        stmt = select(ReliabilityRun)
        if self.organization_id:
            stmt = stmt.where(
                (ReliabilityRun.organization_id == self.organization_id)
                | (ReliabilityRun.organization_id.is_(None))
            )
        stmt = stmt.order_by(desc(ReliabilityRun.created_at)).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # -------------------------------------------------------------------------
    # Faults & Assertions
    # -------------------------------------------------------------------------
    async def add_fault(
        self,
        *,
        run_id: str,
        fault_type: str,
        lifecycle: str,
        injected_at: datetime,
        recovered_at: datetime | None = None,
        parameters: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> ReliabilityFault:
        fault = ReliabilityFault(
            id=str(uuid.uuid4()),
            run_id=run_id,
            fault_type=fault_type,
            lifecycle=lifecycle,
            injected_at=injected_at,
            recovered_at=recovered_at,
            parameters=parameters or {},
            details=details or {},
            created_at=datetime.now(UTC),
        )
        self.db.add(fault)
        await self.db.flush()
        await self.db.refresh(fault)
        return fault

    async def add_assertion(
        self,
        *,
        run_id: str,
        assertion_type: str,
        status: str,
        description: str,
        evidence: dict[str, Any] | None = None,
    ) -> ReliabilityAssertion:
        assertion = ReliabilityAssertion(
            id=str(uuid.uuid4()),
            run_id=run_id,
            assertion_type=assertion_type,
            status=status,
            description=description,
            evidence=evidence or {},
            created_at=datetime.now(UTC),
        )
        self.db.add(assertion)
        await self.db.flush()
        await self.db.refresh(assertion)
        return assertion

    # -------------------------------------------------------------------------
    # Scorecard & Readiness
    # -------------------------------------------------------------------------
    async def save_scorecard(
        self,
        *,
        period_start: datetime,
        period_end: datetime,
        detection_score: float,
        recovery_score: float,
        integrity_score: float,
        degradation_score: float,
        isolation_score: float,
        slo_score: float,
        composite_score: float,
        total_scenarios_run: int,
        passed_count: int,
        failed_count: int,
        metrics_payload: dict[str, Any] | None = None,
    ) -> ReliabilityScorecard:
        scorecard = ReliabilityScorecard(
            id=str(uuid.uuid4()),
            organization_id=self.organization_id,
            period_start=period_start,
            period_end=period_end,
            detection_score=detection_score,
            recovery_score=recovery_score,
            integrity_score=integrity_score,
            degradation_score=degradation_score,
            isolation_score=isolation_score,
            slo_score=slo_score,
            composite_score=composite_score,
            total_scenarios_run=total_scenarios_run,
            passed_count=passed_count,
            failed_count=failed_count,
            metrics_payload=metrics_payload or {},
            created_at=datetime.now(UTC),
        )
        self.db.add(scorecard)
        await self.db.flush()
        await self.db.refresh(scorecard)
        return scorecard

    async def get_latest_scorecard(self) -> ReliabilityScorecard | None:
        stmt = select(ReliabilityScorecard)
        if self.organization_id:
            stmt = stmt.where(
                (ReliabilityScorecard.organization_id == self.organization_id)
                | (ReliabilityScorecard.organization_id.is_(None))
            )
        stmt = stmt.order_by(desc(ReliabilityScorecard.created_at)).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_readiness_record(
        self,
        *,
        decision: str,
        evaluator: str = "automated",
        scorecard_id: str | None = None,
        evaluation_factors: dict[str, Any] | None = None,
        blockers: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> ProductionReadinessRecord:
        record = ProductionReadinessRecord(
            id=str(uuid.uuid4()),
            organization_id=self.organization_id,
            decision=decision,
            evaluator=evaluator,
            scorecard_id=scorecard_id,
            evaluation_factors=evaluation_factors or {},
            blockers=blockers or [],
            warnings=warnings or [],
            created_at=datetime.now(UTC),
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_latest_readiness(self) -> ProductionReadinessRecord | None:
        stmt = select(ProductionReadinessRecord)
        if self.organization_id:
            stmt = stmt.where(
                (ProductionReadinessRecord.organization_id == self.organization_id)
                | (ProductionReadinessRecord.organization_id.is_(None))
            )
        stmt = stmt.order_by(desc(ProductionReadinessRecord.created_at)).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
