"""Payload construction and serialization utilities for vector points."""

import re
from datetime import UTC, datetime
from typing import Any

from app.vectorstore.exceptions import VectorStoreValidationError

_FORBIDDEN_KEY_PATTERNS = re.compile(
    r"(api[_-]?key|password|secret|access_token|refresh_token|auth_token|bearer|private_key|credential|^token$)",
    re.IGNORECASE,
)


class PayloadBuilder:
    """Builds secure, structured metadata payloads for Qdrant vector points.

    Guarantees:
    - Retains all semantic, structural, and model provenance metadata.
    - Stores compact chunk content for rapid retrieval without making Qdrant the sole source.
    - Strips or forbids internal secrets, tokens, or credentials from vector store payloads.
    """

    @classmethod
    def build_chunk_payload(
        cls,
        chunk: Any,
        embedding: Any,
        content: str,
        indexed_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Construct a standardized payload from a DocumentChunk and DocumentChunkEmbedding."""
        org_id = getattr(chunk, "organization_id", None)
        doc_id = getattr(chunk, "document_id", None)
        chunk_id = getattr(chunk, "id", None)

        if not org_id or not doc_id or not chunk_id:
            raise VectorStoreValidationError(
                "Chunk missing required identification fields (organization_id, document_id, id)."
            )

        now_iso = (indexed_at or datetime.now(UTC)).isoformat()

        parent_id = getattr(chunk, "parent_chunk_id", None)
        parent_id_str = str(parent_id) if parent_id is not None else None

        heading_path = getattr(chunk, "heading_path", None)
        if heading_path is None:
            heading_path = []
        elif not isinstance(heading_path, list):
            heading_path = list(heading_path)

        payload: dict[str, Any] = {
            "organization_id": str(org_id),
            "document_id": str(doc_id),
            "chunk_id": str(chunk_id),
            "parent_chunk_id": parent_id_str,
            "chunk_index": int(getattr(chunk, "chunk_index", 0)),
            "chunk_type": str(getattr(chunk, "chunk_type", "text")),
            "page_number": getattr(chunk, "page_number", None),
            "heading_path": [str(h) for h in heading_path],
            "heading_context": getattr(chunk, "heading_context", None),
            "section": getattr(chunk, "section", None),
            "content_hash": str(getattr(chunk, "content_hash", "")),
            "embedding_input_hash": str(getattr(embedding, "embedding_input_hash", "")),
            "embedding_provider": str(getattr(embedding, "provider", "")),
            "embedding_model": str(getattr(embedding, "model", "")),
            "embedding_version": str(getattr(embedding, "version", "1.0.0")),
            "embedding_dimensions": int(getattr(embedding, "dimensions", 1536)),
            "normalization": str(getattr(embedding, "normalization", "l2")),
            "token_count": int(getattr(chunk, "token_count", 0)),
            "character_count": int(getattr(chunk, "character_count", len(content))),
            "chunker_version": str(getattr(chunk, "chunker_version", "1.0.0")),
            "content": content,
            "indexed_at": now_iso,
        }

        # Defensive scan: ensure no sensitive keys leaked into payload
        cls.validate_payload_security(payload)
        return payload

    @classmethod
    def validate_payload_security(cls, payload: dict[str, Any]) -> None:
        """Scan payload keys to prevent accidental leakage of secrets."""
        for k in payload:
            if _FORBIDDEN_KEY_PATTERNS.search(k):
                raise VectorStoreValidationError(
                    f"Forbidden secret or credential key pattern detected in payload key: '{k}'."
                )

    build = build_chunk_payload
