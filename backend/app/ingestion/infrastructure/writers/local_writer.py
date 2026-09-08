"""Local disk dataset storage writer supporting chunked JSONL materialization."""

import json
import uuid
from pathlib import Path
from typing import TextIO

from app.ingestion.domain.models import IngestionChunk
from app.ingestion.domain.protocols import DatasetWriter


class LocalDatasetWriter(DatasetWriter):
    """Persists processed dataset chunks into partitioned local files."""

    def __init__(
        self,
        organization_id: uuid.UUID,
        dataset_id: uuid.UUID,
        version: int,
        base_dir: Path | None = None,
    ) -> None:
        self.organization_id = organization_id
        self.dataset_id = dataset_id
        self.version = version
        self.base_dir = base_dir or Path("storage/datasets")

        self.partition_dir = self.base_dir / str(organization_id) / str(dataset_id) / f"v{version}"
        self.data_file = self.partition_dir / "data.jsonl"
        self._file_handle: TextIO | None = None

    def _ensure_opened(self) -> None:
        if self._file_handle is None:
            self.partition_dir.mkdir(parents=True, exist_ok=True)
            self._file_handle = self.data_file.open("w", encoding="utf-8")

    async def write_chunk(self, chunk: IngestionChunk) -> None:
        """Write rows from chunk as JSONL entries."""
        self._ensure_opened()
        assert self._file_handle is not None

        for row in chunk.rows:
            line = json.dumps(row, default=str, ensure_ascii=False)
            self._file_handle.write(line + "\n")
        self._file_handle.flush()

    async def finalize(self) -> str:
        """Close storage file and return relative storage URI."""
        if self._file_handle is not None:
            self._file_handle.flush()
            self._file_handle.close()
            self._file_handle = None
        else:
            # Empty dataset materialized
            self.partition_dir.mkdir(parents=True, exist_ok=True)
            self.data_file.touch()

        return str(self.data_file)
