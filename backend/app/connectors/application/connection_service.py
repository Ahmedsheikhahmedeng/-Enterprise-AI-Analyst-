"""Connection lifecycle management and testing service."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.domain.enums import ConnectionStatus
from app.connectors.domain.errors import DataSourceNotFoundError
from app.connectors.domain.models import ConnectionTestResult
from app.connectors.infrastructure.registry import ConnectorRegistry, get_connector_registry
from app.connectors.infrastructure.secrets import SecretProvider, get_secret_provider
from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.models.data_source import DataSource

logger = get_logger("connectors.connection_service")


class ConnectionService:
    """Manages connection health tests and connection status lifecycle."""

    def __init__(
        self,
        registry: ConnectorRegistry | None = None,
        secret_provider: SecretProvider | None = None,
    ) -> None:
        self.registry = registry or get_connector_registry()
        self.secret_provider = secret_provider or get_secret_provider()

    async def test_connection(
        self,
        db_session: AsyncSession,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        timeout_seconds: float = 5.0,
    ) -> ConnectionTestResult:
        """Execute live connectivity test, update data source status, and emit audit event."""
        stmt = select(DataSource).where(
            DataSource.id == datasource_id,
            DataSource.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        ds = res.scalars().first()
        if not ds:
            raise DataSourceNotFoundError(datasource_id)

        connector = self.registry.get(ds.type)

        # Decrypt config for connection test
        runtime_config = self.secret_provider.decrypt_config(ds.configuration)

        result = await connector.test_connection(runtime_config, timeout_seconds=timeout_seconds)

        # Update lifecycle status
        old_status = ds.status
        ds.status = (
            ConnectionStatus.ACTIVE.value if result.success else ConnectionStatus.ERROR.value
        )
        ds.updated_at = datetime.now(UTC)

        # Audit log (zero secret leakage)
        audit_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CONNECTION_TESTED",
            resource_type="data_source",
            resource_id=str(datasource_id),
            metadata_={
                "success": result.success,
                "latency_ms": result.latency_ms,
                "previous_status": old_status,
                "new_status": ds.status,
            },
        )
        db_session.add(audit_entry)
        await db_session.commit()
        await db_session.refresh(ds)

        from app.observability.instrumentation.connectors import get_connector_instrumentation

        get_connector_instrumentation().record_connection_test(
            ds.type, result.success, result.latency_ms
        )

        return result
