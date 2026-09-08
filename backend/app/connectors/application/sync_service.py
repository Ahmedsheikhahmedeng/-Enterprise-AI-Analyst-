"""Data source synchronization service managing sync run lifecycle and background jobs."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.domain.enums import SyncStatus
from app.connectors.domain.errors import DataSourceNotFoundError, SyncError
from app.connectors.domain.models import SyncRunModel
from app.connectors.infrastructure.registry import ConnectorRegistry, get_connector_registry
from app.connectors.infrastructure.secrets import SecretProvider, get_secret_provider
from app.core.logging import get_logger
from app.models.audit import AuditLog
from app.models.data_source import DataSource, DataSourceSyncRun

logger = get_logger("connectors.sync_service")


class SyncService:
    """Manages full synchronization lifecycle for data sources."""

    def __init__(
        self,
        registry: ConnectorRegistry | None = None,
        secret_provider: SecretProvider | None = None,
    ) -> None:
        self.registry = registry or get_connector_registry()
        self.secret_provider = secret_provider or get_secret_provider()

    async def execute_sync(
        self,
        db_session: AsyncSession,
        datasource_id: uuid.UUID,
        organization_id: uuid.UUID,
        sync_type: str = "full",
        user_id: uuid.UUID | None = None,
    ) -> SyncRunModel:
        """Execute synchronization run, persist sync run record, and emit audit logs."""
        # 1. Tenant-isolated DataSource lookup
        stmt = select(DataSource).where(
            DataSource.id == datasource_id,
            DataSource.organization_id == organization_id,
        )
        res = await db_session.execute(stmt)
        ds = res.scalars().first()
        if not ds:
            raise DataSourceNotFoundError(datasource_id)

        connector = self.registry.get(ds.type)
        connector.capabilities.require_sync()

        # 2. Create pending sync run record
        sync_run = DataSourceSyncRun(
            organization_id=organization_id,
            data_source_id=datasource_id,
            sync_type=sync_type,
            status=SyncStatus.RUNNING.value,
            started_at=datetime.now(UTC),
            rows_synced=0,
            meta_info={},
        )
        db_session.add(sync_run)
        await db_session.flush()

        # Audit SYNC_STARTED
        db_session.add(
            AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="SYNC_STARTED",
                resource_type="data_source",
                resource_id=str(datasource_id),
                metadata_={"sync_run_id": str(sync_run.id), "sync_type": sync_type},
            )
        )
        await db_session.commit()

        # 3. Perform sync via connector
        runtime_config = self.secret_provider.decrypt_config(ds.configuration)
        try:
            # Full sync discovery / row extraction
            schema = await connector.get_schema(
                datasource_id=datasource_id,
                organization_id=organization_id,
                config=runtime_config,
            )

            total_rows = sum(t.row_count_estimate or 0 for t in schema.tables)
            sync_run.status = SyncStatus.COMPLETED.value
            sync_run.completed_at = datetime.now(UTC)
            sync_run.rows_synced = total_rows
            sync_run.meta_info = {
                "tables_synced": len(schema.tables),
                "connector_type": ds.type,
            }

            db_session.add(
                AuditLog(
                    organization_id=organization_id,
                    user_id=user_id,
                    action="SYNC_COMPLETED",
                    resource_type="data_source",
                    resource_id=str(datasource_id),
                    metadata_={
                        "sync_run_id": str(sync_run.id),
                        "rows_synced": total_rows,
                        "status": sync_run.status,
                    },
                )
            )
            await db_session.commit()
            await db_session.refresh(sync_run)

            from app.observability.instrumentation.connectors import get_connector_instrumentation

            duration_ms = (
                (sync_run.completed_at - sync_run.started_at).total_seconds() * 1000
                if sync_run.completed_at and sync_run.started_at
                else 0.0
            )
            get_connector_instrumentation().record_sync_run(
                ds.type, sync_type, "completed", duration_ms
            )

            return SyncRunModel.model_validate(sync_run)
        except Exception as exc:
            sync_run.status = SyncStatus.FAILED.value
            sync_run.completed_at = datetime.now(UTC)
            sync_run.error_message = str(exc)

            db_session.add(
                AuditLog(
                    organization_id=organization_id,
                    user_id=user_id,
                    action="SYNC_FAILED",
                    resource_type="data_source",
                    resource_id=str(datasource_id),
                    metadata_={
                        "sync_run_id": str(sync_run.id),
                        "error": str(exc),
                    },
                )
            )
            await db_session.commit()
            await db_session.refresh(sync_run)

            from app.observability.instrumentation.connectors import get_connector_instrumentation

            duration_ms = (
                (sync_run.completed_at - sync_run.started_at).total_seconds() * 1000
                if sync_run.completed_at and sync_run.started_at
                else 0.0
            )
            get_connector_instrumentation().record_sync_run(
                ds.type, sync_type, "failed", duration_ms
            )

            raise SyncError(datasource_id, str(exc)) from exc
