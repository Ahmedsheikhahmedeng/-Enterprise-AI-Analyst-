"""RAG adapter for converting tabular dataset rows into retrievable document representations."""

import uuid
from typing import Any

from app.ingestion.domain.enums import IngestionMode


class DatasetRAGAdapter:
    """Formats structured tabular dataset records into textual document cards for RAG search."""

    def format_row_as_document(
        self,
        row: dict[str, Any],
        dataset_name: str,
        row_index: int,
    ) -> str:
        """Render a tabular record as a human-readable key-value card."""
        lines = [f"### Dataset: {dataset_name} (Record #{row_index + 1})"]
        for key, value in row.items():
            display_val = "NULL" if value is None else str(value)
            clean_key = key.replace("_", " ").title()
            lines.append(f"{clean_key}: {display_val}")
        return "\n".join(lines)

    def convert_dataset_to_rag_documents(
        self,
        dataset_id: uuid.UUID,
        dataset_name: str,
        rows: list[dict[str, Any]],
        ingestion_mode: IngestionMode = IngestionMode.STRUCTURED_ONLY,
    ) -> list[dict[str, Any]]:
        """Generate retrievable document representations if RAG is enabled for this dataset."""
        if ingestion_mode not in (IngestionMode.RAG_ENABLED, IngestionMode.BOTH):
            return []

        documents: list[dict[str, Any]] = []
        for idx, row in enumerate(rows):
            doc_text = self.format_row_as_document(row, dataset_name, idx)
            documents.append(
                {
                    "dataset_id": str(dataset_id),
                    "row_index": idx,
                    "content": doc_text,
                    "metadata": {
                        "dataset_id": str(dataset_id),
                        "dataset_name": dataset_name,
                        "row_index": idx,
                    },
                }
            )

        return documents
