"""Quality and integrity validators for intermediate chunks."""

import uuid

from app.chunking.config import ChunkingConfig, default_chunking_config
from app.chunking.exceptions import ChunkingValidationError
from app.chunking.models import ChunkType, IntermediateChunk


def validate_chunks(
    chunks: list[IntermediateChunk],
    expected_document_id: uuid.UUID | None = None,
    expected_organization_id: uuid.UUID | None = None,
    config: ChunkingConfig = default_chunking_config,
) -> None:
    """Validate list of generated IntermediateChunk objects.

    Raises ChunkingValidationError if any integrity, boundary, or hierarchy rule is violated.
    """
    if not chunks:
        return

    chunk_ids: set[uuid.UUID] = set()
    parent_ids: set[uuid.UUID] = set()
    seen_indices: set[int] = set()

    # Pre-collect IDs
    for chunk in chunks:
        if chunk.id in chunk_ids:
            raise ChunkingValidationError(
                f"Duplicate chunk ID detected: {chunk.id}",
                details={"chunk_id": str(chunk.id), "chunk_index": chunk.chunk_index},
            )
        chunk_ids.add(chunk.id)
        if chunk.chunk_type == ChunkType.PARENT:
            parent_ids.add(chunk.id)

    # Validate each chunk
    for chunk in chunks:
        # 1. Non-empty content
        if not chunk.content or not chunk.content.strip():
            raise ChunkingValidationError(
                f"Chunk at index {chunk.chunk_index} has empty or whitespace-only content",
                details={"chunk_index": chunk.chunk_index},
            )

        # 2. Sequential / unique index
        if chunk.chunk_index < 0:
            raise ChunkingValidationError(
                f"Chunk index must be non-negative: {chunk.chunk_index}",
                details={"chunk_index": chunk.chunk_index},
            )
        if chunk.chunk_index in seen_indices:
            raise ChunkingValidationError(
                f"Duplicate chunk index: {chunk.chunk_index}",
                details={"chunk_index": chunk.chunk_index},
            )
        seen_indices.add(chunk.chunk_index)

        # 3. Ownership consistency
        if expected_document_id and chunk.document_id != expected_document_id:
            raise ChunkingValidationError(
                (
                    f"Chunk document_id mismatch: expected {expected_document_id}, "
                    f"got {chunk.document_id}"
                ),
                details={"chunk_id": str(chunk.id)},
            )
        if expected_organization_id and chunk.organization_id != expected_organization_id:
            raise ChunkingValidationError(
                (
                    f"Chunk organization_id mismatch: expected {expected_organization_id}, "
                    f"got {chunk.organization_id}"
                ),
                details={"chunk_id": str(chunk.id)},
            )

        # 4. Character count match
        if chunk.character_count != len(chunk.content):
            raise ChunkingValidationError(
                (
                    f"Character count mismatch at index {chunk.chunk_index}: "
                    f"{chunk.character_count} vs actual {len(chunk.content)}"
                ),
                details={"chunk_index": chunk.chunk_index},
            )

        # 5. Token limits
        if chunk.chunk_type == ChunkType.PARENT:
            if chunk.token_count > config.MAX_PARENT_TOKENS + 50:  # Small buffer for approximation
                raise ChunkingValidationError(
                    (
                        f"Parent chunk at index {chunk.chunk_index} exceeds MAX_PARENT_TOKENS: "
                        f"{chunk.token_count} > {config.MAX_PARENT_TOKENS}"
                    ),
                    details={"chunk_index": chunk.chunk_index, "token_count": chunk.token_count},
                )
        else:
            if chunk.token_count > config.MAX_CHUNK_TOKENS + 50:
                raise ChunkingValidationError(
                    (
                        f"Child chunk at index {chunk.chunk_index} exceeds MAX_CHUNK_TOKENS: "
                        f"{chunk.token_count} > {config.MAX_CHUNK_TOKENS}"
                    ),
                    details={"chunk_index": chunk.chunk_index, "token_count": chunk.token_count},
                )

        # 6. Parent reference validity & cycle prevention
        if chunk.parent_chunk_id is not None:
            if chunk.parent_chunk_id == chunk.id:
                raise ChunkingValidationError(
                    f"Circular parent reference: chunk {chunk.id} references itself",
                    details={"chunk_id": str(chunk.id)},
                )
            if chunk.parent_chunk_id not in chunk_ids:
                raise ChunkingValidationError(
                    (
                        f"Orphan child chunk: parent_chunk_id {chunk.parent_chunk_id} "
                        "not found in chunk batch"
                    ),
                    details={
                        "chunk_id": str(chunk.id),
                        "parent_chunk_id": str(chunk.parent_chunk_id),
                    },
                )
            if chunk.parent_chunk_id not in parent_ids:
                raise ChunkingValidationError(
                    (
                        f"Invalid parent reference: chunk {chunk.parent_chunk_id} "
                        "referenced as parent is not of type PARENT"
                    ),
                    details={
                        "chunk_id": str(chunk.id),
                        "parent_chunk_id": str(chunk.parent_chunk_id),
                    },
                )
        else:
            # If not a child, must be a PARENT chunk or root
            if chunk.chunk_type != ChunkType.PARENT:
                # In flat documents without parent-child grouping, root items may have no parent
                pass
