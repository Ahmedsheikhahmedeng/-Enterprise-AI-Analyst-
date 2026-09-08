"""Lineage tracking, fingerprints, and idempotency service."""

import hashlib
import json
import uuid

from app.ingestion.domain.models import ColumnDefinition, DatasetLineage


class LineageService:
    """Computes deterministic fingerprints and tracks dataset transformation provenance."""

    def compute_source_fingerprint(
        self,
        organization_id: uuid.UUID,
        datasource_id: uuid.UUID | None,
        source_target: str | None = None,
    ) -> str:
        """Compute unique SHA-256 fingerprint for source data origin."""
        raw = f"{organization_id}:{datasource_id}:{source_target or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def compute_schema_fingerprint(self, columns: list[ColumnDefinition]) -> str:
        """Compute structural schema fingerprint from ordered column definitions."""
        cols_summary = [
            {"name": c.normalized_name, "type": c.data_type.value, "nullable": c.nullable}
            for c in sorted(columns, key=lambda x: x.ordinal_position)
        ]
        raw = json.dumps(cols_summary, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def compute_content_fingerprint(self, row_hashes: list[str]) -> str:
        """Compute aggregated dataset content fingerprint from sorted row hashes."""
        sorted_hashes = sorted(row_hashes)
        hasher = hashlib.sha256()
        for h in sorted_hashes:
            hasher.update(h.encode("utf-8"))
        return hasher.hexdigest()

    def create_lineage(
        self,
        dataset_id: uuid.UUID,
        organization_id: uuid.UUID,
        source_datasource_id: uuid.UUID | None,
        columns: list[ColumnDefinition],
        row_hashes: list[str],
        ingestion_job_id: uuid.UUID | None = None,
        source_target: str | None = None,
    ) -> DatasetLineage:
        """Construct canonical DatasetLineage record."""
        source_fp = self.compute_source_fingerprint(
            organization_id, source_datasource_id, source_target
        )
        schema_fp = self.compute_schema_fingerprint(columns)
        content_fp = self.compute_content_fingerprint(row_hashes)

        return DatasetLineage(
            dataset_id=dataset_id,
            source_datasource_id=source_datasource_id,
            organization_id=organization_id,
            source_fingerprint=source_fp,
            schema_fingerprint=schema_fp,
            content_fingerprint=content_fp,
            ingestion_job_id=ingestion_job_id,
        )
