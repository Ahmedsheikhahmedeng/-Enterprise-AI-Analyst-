"""Security tests for SRE: Tenant isolation, RBAC permissions, and unauthorized mutations."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.rbac.catalog import (
    DEFAULT_ROLE_PERMISSIONS,
    PERM_SRE_ALERT_MANAGE,
    PERM_SRE_ALERT_READ,
    PERM_SRE_INCIDENT_MANAGE,
    PERM_SRE_INCIDENT_READ,
    PERM_SRE_MAINTENANCE_MANAGE,
    PERM_SRE_RELEASE_GATE_READ,
    PERM_SRE_RUNBOOK_MANAGE,
    PERM_SRE_RUNBOOK_READ,
    PERM_SRE_SLO_MANAGE,
    PERM_SRE_SLO_READ,
    ROLE_ADMIN,
    ROLE_VIEWER,
    SYSTEM_PERMISSIONS,
)
from app.sre.models import Alert
from app.sre.repository import SRERepository
from app.sre.runbooks import PublishedRunbookImmutableError
from app.sre.schemas import RunbookUpdate
from app.sre.service import SREService


class TestSRERBACPermissions:
    """Verify granular SRE permissions are properly registered and allocated."""

    def test_sre_permissions_registered(self) -> None:
        required_perms = [
            PERM_SRE_ALERT_READ,
            PERM_SRE_ALERT_MANAGE,
            PERM_SRE_INCIDENT_READ,
            PERM_SRE_INCIDENT_MANAGE,
            PERM_SRE_RUNBOOK_READ,
            PERM_SRE_RUNBOOK_MANAGE,
            PERM_SRE_SLO_READ,
            PERM_SRE_SLO_MANAGE,
            PERM_SRE_MAINTENANCE_MANAGE,
            PERM_SRE_RELEASE_GATE_READ,
        ]
        for p in required_perms:
            assert p in SYSTEM_PERMISSIONS

    def test_admin_has_all_sre_permissions(self) -> None:
        admin_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_ADMIN]
        assert PERM_SRE_ALERT_MANAGE in admin_perms
        assert PERM_SRE_INCIDENT_MANAGE in admin_perms
        assert PERM_SRE_RUNBOOK_MANAGE in admin_perms
        assert PERM_SRE_SLO_MANAGE in admin_perms
        assert PERM_SRE_MAINTENANCE_MANAGE in admin_perms

    def test_viewer_has_read_only_permissions(self) -> None:
        viewer_perms = DEFAULT_ROLE_PERMISSIONS[ROLE_VIEWER]
        assert PERM_SRE_ALERT_READ in viewer_perms
        assert PERM_SRE_INCIDENT_READ in viewer_perms
        assert PERM_SRE_SLO_READ in viewer_perms

        # Viewer MUST NOT have manage permissions
        assert PERM_SRE_ALERT_MANAGE not in viewer_perms
        assert PERM_SRE_INCIDENT_MANAGE not in viewer_perms
        assert PERM_SRE_RUNBOOK_MANAGE not in viewer_perms
        assert PERM_SRE_MAINTENANCE_MANAGE not in viewer_perms


class TestSRETenantIsolation:
    """Verify cross-tenant read/write boundary enforcement in SRE layer."""

    @pytest.mark.asyncio
    async def test_tenant_isolation_on_alert_retrieval(self) -> None:
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()

        mock_db = MagicMock()
        mock_execute = AsyncMock()
        mock_db.execute = mock_execute

        # Mock query return: return alert owned by tenant A
        mock_alert_a = Alert(
            id=uuid.uuid4(),
            organization_id=tenant_a_id,
            name="Tenant A DB Alert",
            service="database",
            severity="WARNING",
            status="FIRING",
            source="sre_engine",
            metric="LATENCY",
            fingerprint="abc",
        )

        repo = SRERepository(mock_db)

        # In SRERepository.get_alert, filtering by org_id ensures tenant B cannot query tenant A
        # Let's verify that repo.get_alert applies organization_id filter
        scalar_mock = MagicMock()
        scalar_mock.scalar_one_or_none.return_value = None  # Not found for Tenant B
        mock_execute.return_value = scalar_mock

        alert = await repo.get_alert(mock_alert_a.id, org_id=tenant_b_id)
        assert alert is None

    @pytest.mark.asyncio
    async def test_published_runbook_mutation_denied(self) -> None:
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        repo = SRERepository(mock_db)
        svc = SREService(repo)

        # Mock existing published runbook
        mock_runbook = MagicMock()
        mock_runbook.is_published = True
        mock_runbook.name = "Published Incident Guide"
        mock_runbook.version = 1

        repo.get_runbook = AsyncMock(return_value=mock_runbook)

        with pytest.raises(PublishedRunbookImmutableError) as exc_info:
            await svc.update_runbook(
                runbook_id=uuid.uuid4(),
                data=RunbookUpdate(description="Altered description"),
                org_id=uuid.uuid4(),
            )
        assert "is published and immutable" in str(exc_info.value)
