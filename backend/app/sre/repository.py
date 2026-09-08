"""SRE Repository providing tenant-scoped database access for SRE entities."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.sre.enums import AlertStatusEnum, MaintenanceStatusEnum
from app.sre.models import (
    Alert,
    AlertEvent,
    AlertRule,
    Incident,
    IncidentEvent,
    MaintenanceWindow,
    ReleaseSafetyCheck,
    Runbook,
    SLIDefinition,
    SLODefinition,
)


class SRERepository:
    """Repository managing persistence and retrieval of SRE operational models."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # -----------------------------------------------------------------------
    # SLIs
    # -----------------------------------------------------------------------
    async def list_slis(
        self,
        org_id: uuid.UUID | None,
        service: str | None = None,
    ) -> Sequence[SLIDefinition]:
        stmt = select(SLIDefinition)
        if org_id is not None:
            stmt = stmt.where(
                or_(
                    SLIDefinition.organization_id == org_id, SLIDefinition.organization_id.is_(None)
                )
            )
        else:
            stmt = stmt.where(SLIDefinition.organization_id.is_(None))
        if service:
            stmt = stmt.where(SLIDefinition.service == service)
        stmt = stmt.order_by(SLIDefinition.name)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_sli(self, sli_id: uuid.UUID, org_id: uuid.UUID | None) -> SLIDefinition | None:
        stmt = select(SLIDefinition).where(SLIDefinition.id == sli_id)
        if org_id is not None:
            stmt = stmt.where(
                or_(
                    SLIDefinition.organization_id == org_id, SLIDefinition.organization_id.is_(None)
                )
            )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_sli(self, sli: SLIDefinition) -> SLIDefinition:
        self.db.add(sli)
        await self.db.flush()
        await self.db.refresh(sli)
        return sli

    # -----------------------------------------------------------------------
    # SLOs
    # -----------------------------------------------------------------------
    async def list_slos(
        self,
        org_id: uuid.UUID | None,
        service: str | None = None,
    ) -> Sequence[SLODefinition]:
        stmt = select(SLODefinition)
        if org_id is not None:
            stmt = stmt.where(
                or_(
                    SLODefinition.organization_id == org_id, SLODefinition.organization_id.is_(None)
                )
            )
        else:
            stmt = stmt.where(SLODefinition.organization_id.is_(None))
        if service:
            stmt = stmt.where(SLODefinition.service == service)
        stmt = stmt.order_by(SLODefinition.name)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_slo(self, slo_id: uuid.UUID, org_id: uuid.UUID | None) -> SLODefinition | None:
        stmt = select(SLODefinition).where(SLODefinition.id == slo_id)
        if org_id is not None:
            stmt = stmt.where(
                or_(
                    SLODefinition.organization_id == org_id, SLODefinition.organization_id.is_(None)
                )
            )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_slo(self, slo: SLODefinition) -> SLODefinition:
        self.db.add(slo)
        await self.db.flush()
        return slo

    # -----------------------------------------------------------------------
    # Alert Rules
    # -----------------------------------------------------------------------
    async def list_alert_rules(
        self,
        org_id: uuid.UUID | None,
        service: str | None = None,
    ) -> Sequence[AlertRule]:
        stmt = select(AlertRule)
        if org_id is not None:
            stmt = stmt.where(
                or_(AlertRule.organization_id == org_id, AlertRule.organization_id.is_(None))
            )
        else:
            stmt = stmt.where(AlertRule.organization_id.is_(None))
        if service:
            stmt = stmt.where(AlertRule.service == service)
        stmt = stmt.order_by(AlertRule.name)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_alert_rule(
        self, rule_id: uuid.UUID, org_id: uuid.UUID | None
    ) -> AlertRule | None:
        stmt = select(AlertRule).where(AlertRule.id == rule_id)
        if org_id is not None:
            stmt = stmt.where(
                or_(AlertRule.organization_id == org_id, AlertRule.organization_id.is_(None))
            )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_alert_rule(self, rule: AlertRule) -> AlertRule:
        self.db.add(rule)
        await self.db.flush()
        return rule

    # -----------------------------------------------------------------------
    # Alerts
    # -----------------------------------------------------------------------
    async def list_alerts(
        self,
        org_id: uuid.UUID | None,
        service: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> Sequence[Alert]:
        stmt = select(Alert)
        if org_id is not None:
            stmt = stmt.where(Alert.organization_id == org_id)
        if service:
            stmt = stmt.where(Alert.service == service)
        if status:
            stmt = stmt.where(Alert.status == status)
        if severity:
            stmt = stmt.where(Alert.severity == severity)
        stmt = stmt.order_by(desc(Alert.last_seen_at)).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_alert(self, alert_id: uuid.UUID, org_id: uuid.UUID | None) -> Alert | None:
        stmt = select(Alert).where(Alert.id == alert_id)
        if org_id is not None:
            stmt = stmt.where(Alert.organization_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_firing_alert_by_fingerprint(
        self,
        fingerprint: str,
        org_id: uuid.UUID | None,
    ) -> Alert | None:
        stmt = select(Alert).where(
            Alert.fingerprint == fingerprint,
            Alert.status.in_([AlertStatusEnum.FIRING.value, AlertStatusEnum.ACKNOWLEDGED.value]),
        )
        if org_id is not None:
            stmt = stmt.where(Alert.organization_id == org_id)
        else:
            stmt = stmt.where(Alert.organization_id.is_(None))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_alert(self, alert: Alert) -> Alert:
        self.db.add(alert)
        await self.db.flush()
        return alert

    async def create_alert_event(self, event: AlertEvent) -> AlertEvent:
        self.db.add(event)
        await self.db.flush()
        return event

    async def list_alert_events(
        self,
        alert_id: uuid.UUID,
        org_id: uuid.UUID | None,
    ) -> Sequence[AlertEvent]:
        stmt = select(AlertEvent).where(AlertEvent.alert_id == alert_id)
        if org_id is not None:
            stmt = stmt.where(AlertEvent.organization_id == org_id)
        stmt = stmt.order_by(AlertEvent.created_at)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # -----------------------------------------------------------------------
    # Incidents
    # -----------------------------------------------------------------------
    async def list_incidents(
        self,
        org_id: uuid.UUID | None,
        service: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> Sequence[Incident]:
        stmt = select(Incident)
        if org_id is not None:
            stmt = stmt.where(Incident.organization_id == org_id)
        if service:
            stmt = stmt.where(Incident.service == service)
        if status:
            stmt = stmt.where(Incident.status == status)
        if severity:
            stmt = stmt.where(Incident.severity == severity)
        stmt = stmt.order_by(desc(Incident.opened_at)).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_incident(
        self, incident_id: uuid.UUID, org_id: uuid.UUID | None
    ) -> Incident | None:
        stmt = select(Incident).where(Incident.id == incident_id)
        if org_id is not None:
            stmt = stmt.where(Incident.organization_id == org_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_incident(self, incident: Incident) -> Incident:
        self.db.add(incident)
        await self.db.flush()
        return incident

    async def create_incident_event(self, event: IncidentEvent) -> IncidentEvent:
        self.db.add(event)
        await self.db.flush()
        return event

    async def list_incident_events(
        self,
        incident_id: uuid.UUID,
        org_id: uuid.UUID | None,
    ) -> Sequence[IncidentEvent]:
        stmt = select(IncidentEvent).where(IncidentEvent.incident_id == incident_id)
        if org_id is not None:
            stmt = stmt.where(IncidentEvent.organization_id == org_id)
        stmt = stmt.order_by(IncidentEvent.created_at)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    # -----------------------------------------------------------------------
    # Runbooks
    # -----------------------------------------------------------------------
    async def list_runbooks(
        self,
        org_id: uuid.UUID | None,
        service: str | None = None,
    ) -> Sequence[Runbook]:
        stmt = select(Runbook)
        if org_id is not None:
            stmt = stmt.where(
                or_(Runbook.organization_id == org_id, Runbook.organization_id.is_(None))
            )
        else:
            stmt = stmt.where(Runbook.organization_id.is_(None))
        if service:
            stmt = stmt.where(Runbook.service == service)
        stmt = stmt.order_by(Runbook.name)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_runbook(self, runbook_id: uuid.UUID, org_id: uuid.UUID | None) -> Runbook | None:
        stmt = select(Runbook).where(Runbook.id == runbook_id)
        if org_id is not None:
            stmt = stmt.where(
                or_(Runbook.organization_id == org_id, Runbook.organization_id.is_(None))
            )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_runbook(self, runbook: Runbook) -> Runbook:
        self.db.add(runbook)
        await self.db.flush()
        return runbook

    # -----------------------------------------------------------------------
    # Maintenance Windows
    # -----------------------------------------------------------------------
    async def get_active_maintenance_windows(
        self,
        org_id: uuid.UUID | None,
        now: datetime | None = None,
    ) -> Sequence[MaintenanceWindow]:
        now = now or datetime.now(UTC)
        stmt = select(MaintenanceWindow).where(
            MaintenanceWindow.starts_at <= now,
            MaintenanceWindow.ends_at >= now,
            MaintenanceWindow.status == MaintenanceStatusEnum.ACTIVE.value,
        )
        if org_id is not None:
            stmt = stmt.where(
                or_(
                    MaintenanceWindow.organization_id == org_id,
                    MaintenanceWindow.organization_id.is_(None),
                )
            )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def list_maintenance_windows(
        self,
        org_id: uuid.UUID | None,
    ) -> Sequence[MaintenanceWindow]:
        stmt = select(MaintenanceWindow)
        if org_id is not None:
            stmt = stmt.where(
                or_(
                    MaintenanceWindow.organization_id == org_id,
                    MaintenanceWindow.organization_id.is_(None),
                )
            )
        stmt = stmt.order_by(desc(MaintenanceWindow.starts_at))
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def create_maintenance_window(self, mw: MaintenanceWindow) -> MaintenanceWindow:
        self.db.add(mw)
        await self.db.flush()
        return mw

    # -----------------------------------------------------------------------
    # Release Safety Checks
    # -----------------------------------------------------------------------
    async def create_release_check(self, check: ReleaseSafetyCheck) -> ReleaseSafetyCheck:
        self.db.add(check)
        await self.db.flush()
        return check
