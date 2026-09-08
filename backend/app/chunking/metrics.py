"""Chunk quality and distribution metrics calculation."""

import statistics
import uuid

from app.chunking.config import ChunkingConfig, default_chunking_config
from app.chunking.models import ChunkQualitySummary, ChunkType, IntermediateChunk


def compute_quality_summary(
    chunks: list[IntermediateChunk],
    document_id: uuid.UUID,
    organization_id: uuid.UUID,
    config: ChunkingConfig = default_chunking_config,
) -> ChunkQualitySummary:
    """Compute comprehensive quality metrics and distribution statistics for a chunk batch."""
    if not chunks:
        return ChunkQualitySummary(
            document_id=document_id,
            organization_id=organization_id,
            chunker_version=config.CHUNKER_VERSION,
        )

    total_chunks = len(chunks)
    parent_chunks = 0
    child_chunks = 0
    text_chunks = 0
    table_chunks = 0
    list_chunks = 0
    composite_chunks = 0
    other_chunks = 0
    oversized_chunks = 0
    empty_chunks = 0

    token_counts: list[int] = []
    content_hashes: list[str] = []
    pages_covered: set[int] = set()
    sections_covered: set[str] = set()

    for c in chunks:
        # Counters by type
        if c.chunk_type == ChunkType.PARENT:
            parent_chunks += 1
        elif c.parent_chunk_id is not None:
            child_chunks += 1

        if c.chunk_type == ChunkType.TABLE:
            table_chunks += 1
        elif c.chunk_type == ChunkType.LIST:
            list_chunks += 1
        elif c.chunk_type in (ChunkType.TEXT, ChunkType.PARAGRAPH):
            text_chunks += 1
        elif c.chunk_type == ChunkType.COMPOSITE:
            composite_chunks += 1
        elif c.chunk_type != ChunkType.PARENT:
            other_chunks += 1

        # Content and size checks
        if not c.content or not c.content.strip():
            empty_chunks += 1

        max_allowed = (
            config.MAX_PARENT_TOKENS
            if c.chunk_type == ChunkType.PARENT
            else config.MAX_CHUNK_TOKENS
        )
        if c.token_count > max_allowed:
            oversized_chunks += 1

        token_counts.append(c.token_count)
        content_hashes.append(c.content_hash)

        if c.page_number is not None:
            pages_covered.add(c.page_number)
        if c.section:
            sections_covered.add(c.section)

    # Statistical metrics
    min_tokens = min(token_counts) if token_counts else 0
    max_tokens = max(token_counts) if token_counts else 0
    mean_tokens = round(statistics.mean(token_counts), 2) if token_counts else 0.0
    median_tokens = round(statistics.median(token_counts), 2) if token_counts else 0.0

    # Duplicate ratio
    unique_hashes = len(set(content_hashes))
    duplicate_ratio = (
        round((total_chunks - unique_hashes) / total_chunks, 4) if total_chunks > 0 else 0.0
    )

    return ChunkQualitySummary(
        document_id=document_id,
        organization_id=organization_id,
        chunker_version=config.CHUNKER_VERSION,
        total_chunks=total_chunks,
        parent_chunks=parent_chunks,
        child_chunks=child_chunks,
        text_chunks=text_chunks,
        table_chunks=table_chunks,
        list_chunks=list_chunks,
        composite_chunks=composite_chunks,
        other_chunks=other_chunks,
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        mean_tokens=mean_tokens,
        median_tokens=median_tokens,
        oversized_chunks=oversized_chunks,
        empty_chunks=empty_chunks,
        duplicate_ratio=duplicate_ratio,
        pages_covered=sorted(pages_covered),
        sections_covered=sorted(sections_covered),
    )
