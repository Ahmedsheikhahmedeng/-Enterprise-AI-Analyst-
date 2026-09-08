"""Task adapter for background data source synchronization."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.connectors.application.sync_service import SyncService
from app.connectors.domain.enums import SyncType
from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.workers.ingestion import get_worker_session_factory


class DataSourceSyncTask:
    """Adapts SyncService into standard background TaskHandler interface."""

    def __init__(
        self,
        sync_service: SyncService | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.sync_service = sync_service or SyncService()
        self.session_factory = session_factory

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute full data source synchronization in background worker."""
        raw_ds_id = payload.get("datasource_id")
        if not raw_ds_id:
            raise NonRetryableJobError("Missing required 'datasource_id' in job payload")

        try:
            datasource_id = uuid.UUID(str(raw_ds_id))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid datasource_id format: {raw_ds_id}") from exc

        sync_type_raw = payload.get("sync_type", "full").lower()
        sync_type = SyncType.FULL if sync_type_raw == "full" else SyncType.FULL

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(0.1, "Initializing data source synchronization")

        factory = self.session_factory or get_worker_session_factory()
        async with factory() as session:
            if context.is_cancelled():
                raise JobCancellationError(context.job_id)

            context.report_progress(0.4, "Executing sync on target connector")

            run_model = await self.sync_service.execute_sync(
                db_session=session,
                datasource_id=datasource_id,
                organization_id=context.organization_id,
                sync_type=sync_type.value,
                user_id=None,
            )

            if context.is_cancelled():
                raise JobCancellationError(context.job_id)

            context.report_progress(1.0, "Data source synchronization completed")

            duration_s = 0.0
            if run_model.completed_at and run_model.started_at:
                duration_s = (run_model.completed_at - run_model.started_at).total_seconds()

            return {
                "sync_id": str(run_model.id),
                "datasource_id": str(datasource_id),
                "status": run_model.status.value,
                "sync_type": run_model.sync_type.value,
                "records_synced": run_model.rows_synced,
                "duration_ms": duration_s * 1000,
            }
