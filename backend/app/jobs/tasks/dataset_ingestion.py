"""Background job task handler for Dataset Ingestion and Materialization."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.application.ingestion_service import IngestionService
from app.ingestion.domain.enums import DeduplicationStrategy, IngestionMode
from app.ingestion.domain.models import IngestionConfig
from app.jobs.context import JobContext
from app.jobs.exceptions import JobCancellationError, NonRetryableJobError
from app.workers.ingestion import get_worker_session_factory


class DatasetIngestionTask:
    """Adapts IngestionService into standard background TaskHandler interface."""

    def __init__(
        self,
        ingestion_service: IngestionService | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self.ingestion_service = ingestion_service or IngestionService()
        self.session_factory = session_factory

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        """Execute dataset ingestion in background worker thread."""
        raw_dataset_id = payload.get("dataset_id")
        if not raw_dataset_id:
            raise NonRetryableJobError("Missing required 'dataset_id' in job payload")

        try:
            dataset_id = uuid.UUID(str(raw_dataset_id))
        except ValueError as exc:
            raise NonRetryableJobError(f"Invalid dataset_id format: {raw_dataset_id}") from exc

        if context.is_cancelled():
            raise JobCancellationError(context.job_id)

        # Parse optional configuration
        batch_size = payload.get("batch_size", 1000)
        dedup_raw = payload.get("deduplication_strategy", "exact_row_hash").lower()
        strategy = (
            DeduplicationStrategy(dedup_raw)
            if dedup_raw in DeduplicationStrategy._value2member_map_
            else DeduplicationStrategy.EXACT_ROW_HASH
        )
        mode_raw = payload.get("ingestion_mode", "structured_only").lower()
        mode = (
            IngestionMode(mode_raw)
            if mode_raw in IngestionMode._value2member_map_
            else IngestionMode.STRUCTURED_ONLY
        )

        config = IngestionConfig(
            batch_size=batch_size,
            deduplication_strategy=strategy,
            deduplication_keys=payload.get("deduplication_keys", []),
            ingestion_mode=mode,
            watermark_column=payload.get("watermark_column"),
            last_watermark=payload.get("last_watermark"),
            max_rows=payload.get("max_rows", 1_000_000),
        )

        context.report_progress(0.1, "VALIDATING: Introspecting source schema and tenant bounds")

        factory = self.session_factory or get_worker_session_factory()
        async with factory() as session:
            if context.is_cancelled():
                raise JobCancellationError(context.job_id)

            context.report_progress(0.3, "PROFILING: Scanning and evaluating data distributions")

            if context.is_cancelled():
                raise JobCancellationError(context.job_id)

            context.report_progress(
                0.5, "NORMALIZING: Standardizing identifiers and coercing types"
            )

            if context.is_cancelled():
                raise JobCancellationError(context.job_id)

            context.report_progress(
                0.8, "MATERIALIZING: Storing partitioned data and promoting version"
            )

            result = await self.ingestion_service.ingest_dataset(
                db_session=session,
                organization_id=context.organization_id,
                dataset_id=dataset_id,
                config=config,
                job_id=context.job_id,
                user_id=None,
                target_name=payload.get("target_name"),
            )

            context.report_progress(1.0, "COMPLETED: Dataset materialized successfully")

            return {
                "dataset_id": str(dataset_id),
                "version": result.version,
                "row_count": result.row_count,
                "content_hash": result.content_hash,
                "schema_hash": result.schema_hash,
                "quality_score": result.quality_report.score,
                "status": "completed",
            }
