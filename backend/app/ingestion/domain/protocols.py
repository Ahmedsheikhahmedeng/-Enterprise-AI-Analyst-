"""Protocols and interfaces for Dataset Ingestion, Readers, Writers, and Providers."""

from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.ingestion.domain.models import IngestionChunk


class DatasetReader(Protocol):
    """Protocol for streaming chunks from connectors into the ingestion pipeline."""

    def read_chunks(
        self,
        batch_size: int = 1000,
        max_rows: int = 1_000_000,
        watermark_column: str | None = None,
        last_watermark: str | None = None,
    ) -> AsyncIterator[IngestionChunk]:
        """Stream tabular data in bounded batches."""
        ...


class DatasetWriter(Protocol):
    """Protocol for persisting materialized dataset chunks to durable storage."""

    async def write_chunk(self, chunk: IngestionChunk) -> None:
        """Write a processed chunk to partitioned storage."""
        ...

    async def finalize(self) -> str:
        """Finalize storage writing and return persistent storage URI or path."""
        ...


class IncrementalIngestionProvider(Protocol):
    """Protocol for incremental watermark resolution and delta query construction."""

    def build_watermark_query(
        self,
        base_query: str,
        watermark_column: str,
        last_watermark: Any,
    ) -> str:
        """Construct secure delta query constrained by watermark boundary."""
        ...
