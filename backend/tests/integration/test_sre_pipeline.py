"""Integration tests for end-to-end SRE pipeline: alert ingestion, deduplication, incident FSM, and release safety."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.sre.enums import (
    AlertSeverityEnum,
    AlertStatusEnum,
    IncidentSeverityEnum,
    IncidentStatusEnum,
    ReleaseGateDecisionEnum,
)
from app.sre.repository import SRERepository
from app.sre.schemas import (
    AlertAcknowledgeRequest,
    AlertIngest,
    AlertResolveRequest,
    IncidentCreate,
    IncidentStatusUpdate,
    ReleaseGateEvaluateRequest,
)
from app.sre.service import SREService


class TestSREPipelineIntegration:
    """End-to-end pipeline test across SRE Service & Repository."""

    @pytest.mark.asyncio
    async def test_alert_ingestion_and_deduplication_lifecycle(self) -> None:
        org_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        repo = SRERepository(mock_db)
        svc = SREService(repo)

        # 1. Ingest initial alert
        ingest_data = AlertIngest(
            name="High DB Pool Latency",
            service="database",
            severity=AlertSeverityEnum.WARNING,
            metric="DB_LATENCY",
            source="sre_engine",
            value=650.0,
            threshold=500.0,
        )

        # Mock no existing alert initially
        repo.get_firing_alert_by_fingerprint = AsyncMock(return_value=None)
        repo.get_active_maintenance_windows = AsyncMock(return_value=[])

        alert = await svc.ingest_alert(ingest_data, org_id)
        assert alert.count == 1
        assert alert.status == AlertStatusEnum.FIRING.value
        assert alert.name == "High DB Pool Latency"

        # 2. Ingest duplicate alert with exact same fingerprint
        repo.get_firing_alert_by_fingerprint = AsyncMock(return_value=alert)
        dup_alert = await svc.ingest_alert(ingest_data, org_id)

        assert dup_alert.count == 2
        assert dup_alert.id == alert.id

        # 3. Acknowledge alert
        repo.get_alert = AsyncMock(return_value=dup_alert)
        acked = await svc.acknowledge_alert(
            dup_alert.id,
            AlertAcknowledgeRequest(actor="operator-1", note="Investigating connection spike"),
            org_id,
        )
        assert acked.status == AlertStatusEnum.ACKNOWLEDGED.value

        # 4. Resolve alert
        resolved = await svc.resolve_alert(
            dup_alert.id,
            AlertResolveRequest(actor="operator-1", note="Pool drained and recycled"),
            org_id,
        )
        assert resolved.status == AlertStatusEnum.RESOLVED.value
        assert resolved.ends_at is not None

    @pytest.mark.asyncio
    async def test_incident_full_lifecycle_and_events(self) -> None:
        org_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        repo = SRERepository(mock_db)
        svc = SREService(repo)

        # 1. Create incident
        inc_data = IncidentCreate(
            title="Database Connection Pool Exhaustion Outage",
            service="database",
            severity=IncidentSeverityEnum.SEV2,
            description="Major degradation of write throughput.",
        )
        incident = await svc.create_incident(inc_data, org_id)
        assert incident.status == IncidentStatusEnum.OPEN.value
        assert incident.severity == IncidentSeverityEnum.SEV2.value

        # 2. Transition OPEN -> ACKNOWLEDGED
        repo.get_incident = AsyncMock(return_value=incident)
        acked_inc = await svc.update_incident_status(
            incident.id,
            IncidentStatusUpdate(
                status=IncidentStatusEnum.ACKNOWLEDGED,
                actor="oncall-lead",
                message="Incident acknowledged; commander assigned.",
            ),
            org_id,
        )
        assert acked_inc.status == IncidentStatusEnum.ACKNOWLEDGED.value
        assert acked_inc.acknowledged_at is not None

        # 3. Transition ACKNOWLEDGED -> INVESTIGATING
        inv_inc = await svc.update_incident_status(
            incident.id,
            IncidentStatusUpdate(
                status=IncidentStatusEnum.INVESTIGATING,
                actor="commander",
                message="Isolating long-running transactions.",
            ),
            org_id,
        )
        assert inv_inc.status == IncidentStatusEnum.INVESTIGATING.value

        # 4. Transition INVESTIGATING -> MITIGATED
        mit_inc = await svc.update_incident_status(
            incident.id,
            IncidentStatusUpdate(
                status=IncidentStatusEnum.MITIGATED,
                actor="commander",
                message="Recycled connection pool; write latency normalized.",
            ),
            org_id,
        )
        assert mit_inc.status == IncidentStatusEnum.MITIGATED.value
        assert mit_inc.mitigated_at is not None

        # 5. Transition MITIGATED -> RESOLVED
        res_inc = await svc.update_incident_status(
            incident.id,
            IncidentStatusUpdate(
                status=IncidentStatusEnum.RESOLVED,
                actor="commander",
                message="Service operational; root cause documented.",
                root_cause="Unindexed query locked pg_catalog table.",
                postmortem_url="https://wiki.internal/postmortems/inc-db-01",
            ),
            org_id,
        )
        assert res_inc.status == IncidentStatusEnum.RESOLVED.value
        assert res_inc.resolved_at is not None
        assert res_inc.root_cause is not None

        # 6. Transition RESOLVED -> CLOSED (Terminal)
        closed_inc = await svc.update_incident_status(
            incident.id,
            IncidentStatusUpdate(
                status=IncidentStatusEnum.CLOSED,
                actor="commander",
                message="Postmortem signed off.",
            ),
            org_id,
        )
        assert closed_inc.status == IncidentStatusEnum.CLOSED.value
        assert closed_inc.closed_at is not None

    @pytest.mark.asyncio
    async def test_release_safety_gate_pipeline(self) -> None:
        org_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        repo = SRERepository(mock_db)
        svc = SREService(repo)

        # Baseline check with 0 open incidents -> ALLOW
        repo.list_incidents = AsyncMock(return_value=[])

        check = await svc.evaluate_release_gate(
            ReleaseGateEvaluateRequest(service="database"),
            org_id,
        )
        assert check.decision == ReleaseGateDecisionEnum.ALLOW.value
        assert check.open_incidents_count == 0
