"""Task adapter for background report exports (PDF, HTML, Markdown, CSV)."""

import uuid
from typing import Any

from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.reports.service import ReportService
from app.storage import StorageProvider, get_storage_provider
from app.workers.ingestion import get_worker_session_factory


class ReportExportTask:
    """Adapts ReportService export into standard TaskHandler interface with object storage."""

    def __init__(
        self,
        report_service: ReportService | None = None,
        storage_provider: StorageProvider | None = None,
    ) -> None:
        self.report_service = report_service or ReportService()
        self.storage = storage_provider or get_storage_provider()
        self.session_factory = get_worker_session_factory()

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute report export rendering and save artifact to object storage."""
        raw_report_id = payload.get("report_id")
        if not raw_report_id:
            raise NonRetryableJobError("Missing required 'report_id' in job payload")

        try:
            report_id = uuid.UUID(str(raw_report_id))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid report_id format: {raw_report_id}") from exc

        export_format = str(payload.get("format", "markdown")).lower()
        version_number = payload.get("version_number")

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(0.2, f"Rendering report export ({export_format})")

        async with self.session_factory() as session:
            rendered_content, content_type, filename = await self.report_service.export_report(
                session=session,
                organization_id=context.organization_id,
                report_id=report_id,
                export_format=export_format,
                version_number=int(version_number) if version_number is not None else None,
            )

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        context.report_progress(0.7, "Saving export to object storage")

        # Convert to bytes
        data_bytes = (
            rendered_content
            if isinstance(rendered_content, bytes)
            else rendered_content.encode("utf-8")
        )

        object_key = (
            f"exports/{context.organization_id}/{report_id}_{int(context.attempt)}.{export_format}"
        )
        await self.storage.save(object_key, data_bytes, content_type)

        context.report_progress(1.0, "Report export completed")

        return {
            "report_id": str(report_id),
            "status": "completed",
            "format": export_format,
            "object_key": object_key,
            "size_bytes": len(data_bytes),
        }
