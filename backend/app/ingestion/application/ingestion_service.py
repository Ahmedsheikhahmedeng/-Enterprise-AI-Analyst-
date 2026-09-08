"""High-level orchestration service for Dataset Ingestion and Materialization."""

import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.infrastructure.secrets import SecretProvider
from app.ingestion.application.deduplication_service import DeduplicationService
from app.ingestion.application.lineage_service import LineageService
from app.ingestion.application.materialization_service import MaterializationService
from app.ingestion.application.normalization_service import NormalizationService
from app.ingestion.application.profiling_service import ProfilingService
from app.ingestion.domain.errors import (
    DatasetNotFoundError,
    MaterializationError,
)
from app.ingestion.domain.models import (
    IngestionConfig,
    MaterializationResult,
)
from app.ingestion.infrastructure.readers.connector_reader import ConnectorDatasetReader
from app.ingestion.infrastructure.writers.local_writer import LocalDatasetWriter
from app.models.audit import AuditLog
from app.models.data_source import DataSource
from app.models.dataset import Dataset


class IngestionService:
    """Orchestrates end-to-end dataset ingestion, validation, profiling, and materialization."""

    def __init__(
        self,
        normalization_service: NormalizationService | None = None,
        profiling_service: ProfilingService | None = None,
        deduplication_service: DeduplicationService | None = None,
        lineage_service: LineageService | None = None,
        materialization_service: MaterializationService | None = None,
        secret_provider: SecretProvider | None = None,
    ) -> None:
        self.normalization = normalization_service or NormalizationService()
        self.profiling = profiling_service or ProfilingService()
        self.deduplication = deduplication_service or DeduplicationService()
        self.lineage = lineage_service or LineageService()
        self.materialization = materialization_service or MaterializationService()
        self.secret_provider = secret_provider or SecretProvider()

    async def ingest_dataset(
        self,
        db_session: AsyncSession,
        organization_id: uuid.UUID,
        dataset_id: uuid.UUID,
        config: IngestionConfig | None = None,
        job_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        target_name: str | None = None,
    ) -> MaterializationResult:
        """Run the full ingestion pipeline to materialize a new dataset version."""
        ingestion_config = config or IngestionConfig()
        t0 = time.perf_counter()

        # 1. Fetch Dataset & verify tenant isolation
        ds_stmt = select(Dataset).where(
            Dataset.id == dataset_id,
            Dataset.organization_id == organization_id,
        )
        ds_res = await db_session.execute(ds_stmt)
        dataset = ds_res.scalars().first()
        if not dataset:
            raise DatasetNotFoundError(f"Dataset {dataset_id} not found for this organization")

        # 2. Fetch DataSource if attached
        datasource: DataSource | None = None
        decrypted_config: dict[str, Any] = {}
        if dataset.source_datasource_id:
            src_stmt = select(DataSource).where(
                DataSource.id == dataset.source_datasource_id,
                DataSource.organization_id == organization_id,
            )
            src_res = await db_session.execute(src_stmt)
            datasource = src_res.scalars().first()
            if not datasource:
                raise MaterializationError(
                    f"Source DataSource {dataset.source_datasource_id} not found for this organization"
                )
            decrypted_config = self.secret_provider.decrypt_config(datasource.configuration or {})

        # 3. Create new DatasetVersion in INGESTING state
        version = await self.materialization.prepare_new_version(
            db_session, dataset, job_id=job_id, created_by=user_id
        )

        try:
            # 4. Initialize reader & writer
            reader = ConnectorDatasetReader(
                connector_type=dataset.source_type,
                configuration=decrypted_config,
                datasource_id=dataset.source_datasource_id or dataset.id,
                organization_id=organization_id,
                target_name=target_name,
            )

            writer = LocalDatasetWriter(
                organization_id=organization_id,
                dataset_id=dataset.id,
                version=version.version,
            )

            all_raw_rows: list[dict[str, Any]] = []
            raw_columns: list[str] = []

            # 5. Read chunks
            async for chunk in reader.read_chunks(
                batch_size=ingestion_config.batch_size,
                max_rows=ingestion_config.max_rows,
                watermark_column=ingestion_config.watermark_column,
                last_watermark=ingestion_config.last_watermark,
            ):
                if not raw_columns and chunk.rows:
                    raw_columns = list(chunk.rows[0].keys())
                all_raw_rows.extend(chunk.rows)

            # 6. Normalize schema
            column_defs = self.normalization.normalize_schema(raw_columns)
            col_map = {c.name: c.normalized_name for c in column_defs}

            # 7. Normalize rows
            normalized_rows = [self.normalization.normalize_row(r, col_map) for r in all_raw_rows]

            # 8. Deduplicate
            deduped_rows, duplicate_count = self.deduplication.deduplicate_rows(
                normalized_rows,
                strategy=ingestion_config.deduplication_strategy,
                keys=ingestion_config.deduplication_keys,
            )

            # 9. Profile & Quality
            profile, quality = self.profiling.profile_dataset(
                organization_id=organization_id,
                dataset_id=dataset.id,
                columns=column_defs,
                rows=deduped_rows,
                duplicate_count=duplicate_count,
            )

            # 10. Persist to storage
            from app.ingestion.domain.models import IngestionChunk

            processed_chunk = IngestionChunk(
                chunk_index=0,
                rows=deduped_rows,
                row_count=len(deduped_rows),
            )
            await writer.write_chunk(processed_chunk)
            storage_path = await writer.finalize()

            # 11. Compute fingerprints & lineage
            row_hashes = [self.deduplication.compute_row_hash(r) for r in deduped_rows]
            content_hash = self.lineage.compute_content_fingerprint(row_hashes)
            schema_hash = self.lineage.compute_schema_fingerprint(column_defs)

            lineage = self.lineage.create_lineage(
                dataset_id=dataset.id,
                organization_id=organization_id,
                source_datasource_id=dataset.source_datasource_id,
                columns=column_defs,
                row_hashes=row_hashes,
                ingestion_job_id=job_id,
                source_target=target_name,
            )

            # 12. Determine security classification
            pii_map = {c.normalized_name: c.pii_classification for c in column_defs}
            classification = self.profiling.pii_detector.determine_dataset_classification(pii_map)
            dataset.classification = classification.value

            # 13. Materialize & promote version to READY
            await self.materialization.promote_version_success(
                db_session=db_session,
                dataset=dataset,
                version=version,
                columns=column_defs,
                profile=profile,
                quality_report=quality,
                lineage=lineage,
                storage_path=storage_path,
                content_hash=content_hash,
                schema_hash=schema_hash,
                row_count=len(deduped_rows),
            )

            duration_s = time.perf_counter() - t0

            # 14. Audit Log
            audit_entry = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="INGESTION_COMPLETED",
                resource_type="dataset",
                resource_id=str(dataset.id),
                metadata_={
                    "version": version.version,
                    "row_count": len(deduped_rows),
                    "quality_score": quality.score,
                    "duration_seconds": round(duration_s, 2),
                },
            )
            db_session.add(audit_entry)
            await db_session.commit()

            # 15. Record Metrics
            from app.observability.instrumentation.datasets import get_dataset_instrumentation

            get_dataset_instrumentation().record_ingestion_completed(
                dataset.source_type, len(deduped_rows), duration_s, quality.score
            )

            return MaterializationResult(
                dataset_id=dataset.id,
                version=version.version,
                row_count=len(deduped_rows),
                content_hash=content_hash,
                schema_hash=schema_hash,
                storage_path=storage_path,
                profile=profile,
                quality_report=quality,
                lineage=lineage,
                classification=classification,
            )

        except Exception as exc:
            duration_s = time.perf_counter() - t0
            await self.materialization.mark_version_failure(db_session, dataset, version, str(exc))

            # Audit failure without leaking secrets
            audit_entry = AuditLog(
                organization_id=organization_id,
                user_id=user_id,
                action="INGESTION_FAILED",
                resource_type="dataset",
                resource_id=str(dataset.id),
                metadata_={
                    "version": version.version,
                    "error": str(exc),
                    "duration_seconds": round(duration_s, 2),
                },
            )
            db_session.add(audit_entry)
            await db_session.commit()

            from app.observability.instrumentation.datasets import get_dataset_instrumentation

            get_dataset_instrumentation().record_ingestion_failed(dataset.source_type)
            raise
