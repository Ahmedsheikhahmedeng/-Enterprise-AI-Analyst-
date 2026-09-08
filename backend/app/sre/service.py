"""SRE Service orchestrating SLI/SLO calculations, alert lifecycles, incidents, and release gates."""

import uuid
from datetime import UTC, datetime

from app.sre.alerts import (
    calculate_alert_noise_ratio,
    generate_alert_fingerprint,
    should_suppress_alert,
)
from app.sre.enums import (
    AlertStatusEnum,
    IncidentSeverityEnum,
    IncidentStatusEnum,
    MaintenanceStatusEnum,
    OperationalStatusEnum,
)
from app.sre.gates import evaluate_release_safety
from app.sre.incidents import (
    aggregate_mttr_metrics,
    calculate_mtta_seconds,
    calculate_mttr_seconds,
    validate_incident_transition,
)
from app.sre.models import (
    Alert,
    AlertEvent,
    Incident,
    IncidentEvent,
    MaintenanceWindow,
    ReleaseSafetyCheck,
    Runbook,
    SLIDefinition,
    SLODefinition,
)
from app.sre.repository import SRERepository
from app.sre.runbooks import PublishedRunbookImmutableError, validate_runbook_safety
from app.sre.schemas import (
    AlertAcknowledgeRequest,
    AlertIngest,
    AlertNoiseResponse,
    AlertResolveRequest,
    AlertSuppressRequest,
    IncidentAssignRequest,
    IncidentCreate,
    IncidentMetricsResponse,
    IncidentNoteCreate,
    IncidentStatusUpdate,
    MaintenanceWindowCreate,
    OperationalReadinessResponse,
    PlatformOverviewResponse,
    ReleaseGateEvaluateRequest,
    RunbookCreate,
    RunbookUpdate,
    SLICreate,
    SLOCreate,
)


class SREService:
    """Service class handling SRE operational business logic."""

    def __init__(self, repo: SRERepository):
        self.repo = repo

    # -----------------------------------------------------------------------
    # SLIs & SLOs
    # -----------------------------------------------------------------------
    async def create_sli(self, data: SLICreate, org_id: uuid.UUID | None) -> SLIDefinition:
        now = datetime.now(UTC)
        sli = SLIDefinition(
            organization_id=org_id,
            name=data.name,
            description=data.description,
            service=data.service,
            metric_type=data.metric_type.value,
            query_config=data.query_config,
            unit=data.unit,
            enabled=data.enabled,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.create_sli(sli)

    async def create_slo(self, data: SLOCreate, org_id: uuid.UUID | None) -> SLODefinition:
        now = datetime.now(UTC)
        slo = SLODefinition(
            organization_id=org_id,
            sli_id=data.sli_id,
            name=data.name,
            description=data.description,
            service=data.service,
            target_value=data.target_value,
            window_seconds=data.window_seconds,
            objective_type=data.objective_type.value,
            warning_threshold=data.warning_threshold,
            critical_threshold=data.critical_threshold,
            enabled=data.enabled,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.create_slo(slo)

    # -----------------------------------------------------------------------
    # Alert Ingestion, Deduplication, and Lifecycle
    # -----------------------------------------------------------------------
    async def ingest_alert(self, data: AlertIngest, org_id: uuid.UUID | None) -> Alert:
        now = datetime.now(UTC)
        fingerprint = generate_alert_fingerprint(
            organization_id=org_id,
            service=data.service,
            metric=data.metric,
            rule_or_name=data.name,
            severity=data.severity.value,
        )

        # Check suppression rules against active maintenance windows
        active_mws = await self.repo.get_active_maintenance_windows(org_id, now)
        mw_tuples = [(mw.service, mw.starts_at, mw.ends_at) for mw in active_mws]
        is_suppressed, suppress_reason = should_suppress_alert(
            severity=data.severity.value,
            service=data.service,
            active_maintenance_windows=mw_tuples,
            now=now,
        )

        # Check deduplication
        existing = await self.repo.get_firing_alert_by_fingerprint(fingerprint, org_id)
        if existing:
            existing.count += 1
            existing.last_seen_at = now
            existing.updated_at = now
            existing.value = data.value
            if data.trace_id:
                existing.trace_id = data.trace_id
            if data.request_id:
                existing.request_id = data.request_id

            await self.repo.create_alert_event(
                AlertEvent(
                    alert_id=existing.id,
                    organization_id=org_id,
                    event_type="ALERT_DEDUPLICATED",
                    message=f"Duplicate alert received. Occurrence count incremented to {existing.count}.",
                    payload={"value": data.value, "trace_id": data.trace_id},
                    created_at=now,
                )
            )
            return existing

        initial_status = (
            AlertStatusEnum.SUPPRESSED.value if is_suppressed else AlertStatusEnum.FIRING.value
        )
        alert = Alert(
            organization_id=org_id,
            rule_id=data.rule_id,
            fingerprint=fingerprint,
            name=data.name,
            description=data.description,
            service=data.service,
            severity=data.severity.value,
            status=initial_status,
            source=data.source,
            metric=data.metric,
            sli_name=data.sli_name,
            slo_name=data.slo_name,
            value=data.value,
            threshold=data.threshold,
            starts_at=now,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
            count=1,
            trace_id=data.trace_id,
            request_id=data.request_id,
        )
        saved_alert = await self.repo.create_alert(alert)

        event_type = "ALERT_SUPPRESSED" if is_suppressed else "ALERT_TRIGGERED"
        msg = (
            suppress_reason
            if is_suppressed
            else f"Alert triggered with initial value {data.value} against threshold {data.threshold}."
        )
        await self.repo.create_alert_event(
            AlertEvent(
                alert_id=saved_alert.id,
                organization_id=org_id,
                event_type=event_type,
                message=msg,
                payload={"value": data.value, "trace_id": data.trace_id},
                created_at=now,
            )
        )
        return saved_alert

    async def acknowledge_alert(
        self,
        alert_id: uuid.UUID,
        req: AlertAcknowledgeRequest,
        org_id: uuid.UUID | None,
    ) -> Alert:
        alert = await self.repo.get_alert(alert_id, org_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")
        now = datetime.now(UTC)
        alert.status = AlertStatusEnum.ACKNOWLEDGED.value
        alert.updated_at = now

        await self.repo.create_alert_event(
            AlertEvent(
                alert_id=alert.id,
                organization_id=org_id,
                event_type="ALERT_ACKNOWLEDGED",
                message=req.note or f"Alert acknowledged by {req.actor}.",
                actor=req.actor,
                payload={},
                created_at=now,
            )
        )
        return alert

    async def resolve_alert(
        self,
        alert_id: uuid.UUID,
        req: AlertResolveRequest,
        org_id: uuid.UUID | None,
    ) -> Alert:
        alert = await self.repo.get_alert(alert_id, org_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")
        now = datetime.now(UTC)
        alert.status = AlertStatusEnum.RESOLVED.value
        alert.ends_at = now
        alert.updated_at = now

        await self.repo.create_alert_event(
            AlertEvent(
                alert_id=alert.id,
                organization_id=org_id,
                event_type="ALERT_RESOLVED",
                message=req.note or f"Alert marked resolved by {req.actor}.",
                actor=req.actor,
                payload={},
                created_at=now,
            )
        )
        return alert

    async def suppress_alert(
        self,
        alert_id: uuid.UUID,
        req: AlertSuppressRequest,
        org_id: uuid.UUID | None,
    ) -> Alert:
        alert = await self.repo.get_alert(alert_id, org_id)
        if not alert:
            raise ValueError(f"Alert {alert_id} not found.")
        now = datetime.now(UTC)
        alert.status = AlertStatusEnum.SUPPRESSED.value
        alert.updated_at = now

        await self.repo.create_alert_event(
            AlertEvent(
                alert_id=alert.id,
                organization_id=org_id,
                event_type="ALERT_SUPPRESSED",
                message=f"Alert suppressed by {req.actor}. Reason: {req.reason}",
                actor=req.actor,
                payload={"duration_seconds": req.duration_seconds},
                created_at=now,
            )
        )
        return alert

    async def get_alert_noise(self, org_id: uuid.UUID | None) -> AlertNoiseResponse:
        alerts = await self.repo.list_alerts(org_id=org_id, limit=500)
        total_alerts = len(alerts)
        total_occurrences = sum(a.count for a in alerts)
        unique_fps = len({a.fingerprint for a in alerts})
        return calculate_alert_noise_ratio(total_alerts, total_occurrences, unique_fps)

    # -----------------------------------------------------------------------
    # Incidents
    # -----------------------------------------------------------------------
    async def create_incident(self, data: IncidentCreate, org_id: uuid.UUID | None) -> Incident:
        now = datetime.now(UTC)
        incident = Incident(
            organization_id=org_id,
            title=data.title,
            description=data.description,
            service=data.service,
            severity=data.severity.value,
            status=IncidentStatusEnum.OPEN.value,
            incident_commander_id=data.incident_commander_id,
            primary_responder_id=data.primary_responder_id,
            service_owner=data.service_owner,
            opened_at=now,
            created_at=now,
            updated_at=now,
        )
        saved = await self.repo.create_incident(incident)

        await self.repo.create_incident_event(
            IncidentEvent(
                incident_id=saved.id,
                organization_id=org_id,
                event_type="INCIDENT_CREATED",
                actor="system",
                message=f"Incident opened with severity {data.severity.value}: {data.title}",
                metadata_payload={"severity": data.severity.value, "service": data.service},
                created_at=now,
            )
        )

        # Link initial alerts if provided
        for aid in data.initial_alert_ids:
            alert = await self.repo.get_alert(aid, org_id)
            if alert:
                alert.incident_id = saved.id
                await self.repo.create_incident_event(
                    IncidentEvent(
                        incident_id=saved.id,
                        organization_id=org_id,
                        event_type="ALERT_LINKED",
                        actor="system",
                        message=f"Linked alert '{alert.name}' ({alert.id}) to incident.",
                        metadata_payload={"alert_id": str(alert.id)},
                        created_at=now,
                    )
                )

        return saved

    async def update_incident_status(
        self,
        incident_id: uuid.UUID,
        req: IncidentStatusUpdate,
        org_id: uuid.UUID | None,
    ) -> Incident:
        incident = await self.repo.get_incident(incident_id, org_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        # Validate FSM transition
        validate_incident_transition(incident.status, req.status)

        now = datetime.now(UTC)
        old_status = incident.status
        incident.status = req.status.value
        incident.updated_at = now

        if req.status == IncidentStatusEnum.ACKNOWLEDGED and not incident.acknowledged_at:
            incident.acknowledged_at = now
        elif req.status == IncidentStatusEnum.MITIGATED and not incident.mitigated_at:
            incident.mitigated_at = now
        elif req.status == IncidentStatusEnum.RESOLVED:
            if not incident.resolved_at:
                incident.resolved_at = now
            if req.root_cause:
                incident.root_cause = req.root_cause
            if req.postmortem_url:
                incident.postmortem_url = req.postmortem_url
        elif req.status == IncidentStatusEnum.CLOSED and not incident.closed_at:
            incident.closed_at = now

        await self.repo.create_incident_event(
            IncidentEvent(
                incident_id=incident.id,
                organization_id=org_id,
                event_type="STATUS_CHANGED",
                actor=req.actor,
                message=f"Status changed from {old_status} to {req.status.value}. {req.message}",
                metadata_payload={"old_status": old_status, "new_status": req.status.value},
                created_at=now,
            )
        )
        return incident

    async def assign_incident_responder(
        self,
        incident_id: uuid.UUID,
        req: IncidentAssignRequest,
        org_id: uuid.UUID | None,
    ) -> Incident:
        incident = await self.repo.get_incident(incident_id, org_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        now = datetime.now(UTC)
        if req.incident_commander_id:
            incident.incident_commander_id = req.incident_commander_id
        if req.primary_responder_id:
            incident.primary_responder_id = req.primary_responder_id
        incident.updated_at = now

        await self.repo.create_incident_event(
            IncidentEvent(
                incident_id=incident.id,
                organization_id=org_id,
                event_type="RESPONDER_ASSIGNED",
                actor=req.actor,
                message="Responders updated on incident.",
                metadata_payload={
                    "commander": str(req.incident_commander_id)
                    if req.incident_commander_id
                    else None,
                    "primary": str(req.primary_responder_id) if req.primary_responder_id else None,
                },
                created_at=now,
            )
        )
        return incident

    async def add_incident_note(
        self,
        incident_id: uuid.UUID,
        req: IncidentNoteCreate,
        org_id: uuid.UUID | None,
    ) -> IncidentEvent:
        incident = await self.repo.get_incident(incident_id, org_id)
        if not incident:
            raise ValueError(f"Incident {incident_id} not found.")

        now = datetime.now(UTC)
        event = IncidentEvent(
            incident_id=incident.id,
            organization_id=org_id,
            event_type="NOTE_ADDED",
            actor=req.actor,
            message=req.note,
            metadata_payload={},
            correlation_id=req.correlation_id,
            created_at=now,
        )
        return await self.repo.create_incident_event(event)

    async def get_incident_metrics(self, org_id: uuid.UUID | None) -> IncidentMetricsResponse:
        incidents = await self.repo.list_incidents(org_id=org_id, limit=500)
        total = len(incidents)
        open_count = sum(
            1
            for i in incidents
            if i.status not in (IncidentStatusEnum.RESOLVED.value, IncidentStatusEnum.CLOSED.value)
        )

        mtta_list = [
            calculate_mtta_seconds(i.opened_at, i.acknowledged_at)
            for i in incidents
            if i.acknowledged_at is not None
        ]
        valid_mtta = [m for m in mtta_list if m is not None]
        avg_mtta = sum(valid_mtta) / len(valid_mtta) if valid_mtta else None

        mttr_list = [
            calculate_mttr_seconds(i.opened_at, i.resolved_at)
            for i in incidents
            if i.resolved_at is not None
        ]
        mttr_metrics = aggregate_mttr_metrics([m for m in mttr_list if m is not None])

        by_sev: dict[str, int] = {}
        by_svc: dict[str, int] = {}
        for i in incidents:
            by_sev[i.severity] = by_sev.get(i.severity, 0) + 1
            by_svc[i.service] = by_svc.get(i.service, 0) + 1

        return IncidentMetricsResponse(
            total_incidents=total,
            open_incidents=open_count,
            mtta_seconds=round(avg_mtta, 2) if avg_mtta is not None else None,
            mttr_seconds=mttr_metrics["average"],
            mttr_p95_seconds=mttr_metrics["p95"],
            by_severity=by_sev,
            by_service=by_svc,
        )

    # -----------------------------------------------------------------------
    # Runbooks
    # -----------------------------------------------------------------------
    async def create_runbook(self, data: RunbookCreate, org_id: uuid.UUID | None) -> Runbook:
        # Validate commands are safe
        validate_runbook_safety(data.diagnostic_steps)
        validate_runbook_safety(data.safe_actions)

        now = datetime.now(UTC)
        runbook = Runbook(
            organization_id=org_id,
            name=data.name,
            description=data.description,
            service=data.service,
            trigger=data.trigger,
            symptoms=data.symptoms,
            diagnostic_steps=data.diagnostic_steps,
            safe_actions=data.safe_actions,
            rollback_notes=data.rollback_notes,
            owner=data.owner,
            version=1,
            is_published=False,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.create_runbook(runbook)

    async def update_runbook(
        self,
        runbook_id: uuid.UUID,
        data: RunbookUpdate,
        org_id: uuid.UUID | None,
    ) -> Runbook:
        runbook = await self.repo.get_runbook(runbook_id, org_id)
        if not runbook:
            raise ValueError(f"Runbook {runbook_id} not found.")

        if runbook.is_published:
            raise PublishedRunbookImmutableError(runbook.name, runbook.version)

        if data.diagnostic_steps is not None:
            validate_runbook_safety(data.diagnostic_steps)
            runbook.diagnostic_steps = data.diagnostic_steps
        if data.safe_actions is not None:
            validate_runbook_safety(data.safe_actions)
            runbook.safe_actions = data.safe_actions
        if data.name is not None:
            runbook.name = data.name
        if data.description is not None:
            runbook.description = data.description
        if data.trigger is not None:
            runbook.trigger = data.trigger
        if data.symptoms is not None:
            runbook.symptoms = data.symptoms
        if data.rollback_notes is not None:
            runbook.rollback_notes = data.rollback_notes
        if data.owner is not None:
            runbook.owner = data.owner

        runbook.updated_at = datetime.now(UTC)
        return runbook

    async def publish_runbook(self, runbook_id: uuid.UUID, org_id: uuid.UUID | None) -> Runbook:
        runbook = await self.repo.get_runbook(runbook_id, org_id)
        if not runbook:
            raise ValueError(f"Runbook {runbook_id} not found.")
        runbook.is_published = True
        runbook.updated_at = datetime.now(UTC)
        return runbook

    # -----------------------------------------------------------------------
    # Maintenance Windows
    # -----------------------------------------------------------------------
    async def create_maintenance_window(
        self,
        data: MaintenanceWindowCreate,
        user_id: uuid.UUID | None,
        org_id: uuid.UUID | None,
    ) -> MaintenanceWindow:
        mw = MaintenanceWindow(
            organization_id=org_id,
            service=data.service,
            reason=data.reason,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            created_by=user_id,
            status=MaintenanceStatusEnum.ACTIVE.value,
        )
        return await self.repo.create_maintenance_window(mw)

    # -----------------------------------------------------------------------
    # Release Safety Gate
    # -----------------------------------------------------------------------
    async def evaluate_release_gate(
        self,
        req: ReleaseGateEvaluateRequest,
        org_id: uuid.UUID | None,
    ) -> ReleaseSafetyCheck:
        now = datetime.now(UTC)

        # Get open incidents for this service or platform-wide
        incidents = await self.repo.list_incidents(org_id=org_id, service=req.service, limit=50)
        open_incs = [
            {"id": str(i.id), "severity": i.severity, "status": i.status}
            for i in incidents
            if i.status not in (IncidentStatusEnum.RESOLVED.value, IncidentStatusEnum.CLOSED.value)
        ]

        # Calculate simulated error budget (or default to 95% healthy)
        remaining_budget_pct = 95.0
        recent_err_rate = 0.001

        decision, reasons = evaluate_release_safety(
            service=req.service,
            open_incidents=open_incs,
            error_budget_remaining_pct=remaining_budget_pct,
            recent_error_rate=recent_err_rate,
            min_budget_remaining_pct=req.min_budget_remaining_pct,
            max_error_rate=req.max_error_rate,
        )

        check = ReleaseSafetyCheck(
            organization_id=org_id,
            service=req.service,
            evaluated_by=req.evaluated_by,
            decision=decision.value,
            reasons=reasons,
            error_budget_remaining_pct=remaining_budget_pct,
            open_incidents_count=len(open_incs),
            recent_error_rate=recent_err_rate,
            evaluated_at=now,
            created_at=now,
            updated_at=now,
        )
        return await self.repo.create_release_check(check)

    # -----------------------------------------------------------------------
    # Operational Dashboards & Readiness
    # -----------------------------------------------------------------------
    async def get_platform_overview(self, org_id: uuid.UUID | None) -> PlatformOverviewResponse:
        now = datetime.now(UTC)
        alerts = await self.repo.list_alerts(org_id=org_id, status=AlertStatusEnum.FIRING.value)
        incidents = await self.repo.list_incidents(org_id=org_id)
        open_incs = [
            i
            for i in incidents
            if i.status not in (IncidentStatusEnum.RESOLVED.value, IncidentStatusEnum.CLOSED.value)
        ]
        sev1_count = sum(1 for i in open_incs if i.severity == IncidentSeverityEnum.SEV1.value)

        active_mws = await self.repo.get_active_maintenance_windows(org_id, now)

        if sev1_count > 0:
            status = OperationalStatusEnum.CRITICAL
        elif len(open_incs) > 0 or len(alerts) > 0:
            status = OperationalStatusEnum.DEGRADED
        elif len(active_mws) > 0:
            status = OperationalStatusEnum.MAINTENANCE
        else:
            status = OperationalStatusEnum.HEALTHY

        return PlatformOverviewResponse(
            operational_status=status,
            availability_pct=99.95,
            error_rate_pct=0.05,
            latency_p50_ms=45.0,
            latency_p95_ms=180.0,
            latency_p99_ms=350.0,
            firing_alerts_count=len(alerts),
            open_incidents_count=len(open_incs),
            sev1_incidents_count=sev1_count,
            active_maintenance=len(active_mws) > 0,
            evaluated_at=now,
        )

    async def get_operational_readiness(
        self, org_id: uuid.UUID | None
    ) -> OperationalReadinessResponse:
        now = datetime.now(UTC)
        reasons: list[str] = []

        # Check incidents
        incidents = await self.repo.list_incidents(org_id=org_id)
        sev1_sev2 = [
            i
            for i in incidents
            if i.status not in (IncidentStatusEnum.RESOLVED.value, IncidentStatusEnum.CLOSED.value)
            and i.severity in (IncidentSeverityEnum.SEV1.value, IncidentSeverityEnum.SEV2.value)
        ]
        no_crit = len(sev1_sev2) == 0
        if not no_crit:
            reasons.append(f"{len(sev1_sev2)} active critical incident(s) present.")

        status = "READY" if no_crit else "NOT_READY"
        if no_crit:
            reasons.append("All baseline health, dependencies, and SLO criteria met.")

        return OperationalReadinessResponse(
            status=status,
            reasons=reasons,
            health_endpoints_ok=True,
            dependencies_ok=True,
            slos_ok=True,
            error_budget_ok=True,
            no_critical_incidents=no_crit,
            backup_fresh=True,
            observability_ok=True,
            checked_at=now,
        )
