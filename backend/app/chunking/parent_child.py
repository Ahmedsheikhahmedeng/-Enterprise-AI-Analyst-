"""Parent and child chunk hierarchy generation.

Builds two-tier retrieval representations:
- Parent chunks: Broad context (e.g. section-level group, up to MAX_PARENT_TOKENS).
- Child chunks: Granular retrieval units referencing parent_chunk_id.
"""

import uuid

from app.chunking.config import ChunkingConfig, default_chunking_config
from app.chunking.hashing import (
    compute_content_hash,
    generate_deterministic_chunk_id,
)
from app.chunking.models import ChunkType, IntermediateChunk, SourceLocator
from app.chunking.strategies import RawChunkItem
from app.chunking.tokenizer import TokenCounter, default_token_counter


class ParentChildGenerator:
    """Generates parent-child chunk hierarchies from raw chunk items."""

    def __init__(
        self,
        config: ChunkingConfig = default_chunking_config,
        token_counter: TokenCounter = default_token_counter,
    ) -> None:
        self.config = config
        self.token_counter = token_counter

    def build_hierarchy(
        self,
        raw_items: list[RawChunkItem],
        document_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> list[IntermediateChunk]:
        """Convert raw items into an indexed, validated parent-child list of IntermediateChunks."""
        if not raw_items:
            return []

        # Group raw items by section / top heading
        grouped_items: list[list[RawChunkItem]] = []
        current_group: list[RawChunkItem] = []
        current_section: str | None = None

        for item in raw_items:
            # Section identification preference: item.section or top heading_path element
            sec_key = item.section or (item.heading_path[0] if item.heading_path else "Default")
            if current_group and sec_key != current_section:
                grouped_items.append(current_group)
                current_group = [item]
                current_section = sec_key
            else:
                current_group.append(item)
                current_section = sec_key

        if current_group:
            grouped_items.append(current_group)

        final_chunks: list[IntermediateChunk] = []
        global_chunk_index = 0

        for group in grouped_items:
            # Determine parent properties
            first_item = group[0]
            group_heading_path = list(first_item.heading_path)
            group_heading_context = first_item.heading_context
            group_section = first_item.section
            group_page = first_item.page_number

            # Synthesize parent text (concatenation up to MAX_PARENT_TOKENS)
            parent_text_parts: list[str] = []
            for item in group:
                parent_text_parts.append(item.content)

            combined_parent_text = "\n\n".join(parent_text_parts)
            parent_tokens = self.token_counter.count_tokens(combined_parent_text)

            # If parent text is larger than MAX_PARENT_TOKENS, truncate safely to tokens
            if parent_tokens > self.config.MAX_PARENT_TOKENS:
                combined_parent_text = self.token_counter.truncate_to_tokens(
                    combined_parent_text, self.config.MAX_PARENT_TOKENS
                )
                parent_tokens = self.token_counter.count_tokens(combined_parent_text)

            parent_hash = compute_content_hash(combined_parent_text)
            parent_id = generate_deterministic_chunk_id(
                document_id=document_id,
                chunk_index=global_chunk_index,
                chunker_version=self.config.CHUNKER_VERSION,
                content_hash=parent_hash,
            )

            parent_chunk = IntermediateChunk(
                id=parent_id,
                document_id=document_id,
                organization_id=organization_id,
                parent_chunk_id=None,
                chunk_index=global_chunk_index,
                chunk_type=ChunkType.PARENT,
                content=combined_parent_text,
                heading_context=group_heading_context,
                heading_path=group_heading_path,
                page_number=group_page,
                section=group_section,
                source_locator=SourceLocator(
                    document_id=document_id,
                    page_number=group_page,
                    section_title=group_section,
                ).model_dump(mode="json"),
                token_count=parent_tokens,
                character_count=len(combined_parent_text),
                content_hash=parent_hash,
                chunker_version=self.config.CHUNKER_VERSION,
                metadata={
                    "is_parent": True,
                    "child_count": len(group),
                },
            )
            final_chunks.append(parent_chunk)
            global_chunk_index += 1

            # Build children referencing parent_id
            for child_item in group:
                child_hash = compute_content_hash(child_item.content)
                child_tokens = self.token_counter.count_tokens(child_item.content)
                child_id = generate_deterministic_chunk_id(
                    document_id=document_id,
                    chunk_index=global_chunk_index,
                    chunker_version=self.config.CHUNKER_VERSION,
                    content_hash=child_hash,
                )

                child_locator = (
                    child_item.source_locator.model_dump(mode="json")
                    if isinstance(child_item.source_locator, SourceLocator)
                    else (child_item.source_locator or {})
                )

                child_chunk = IntermediateChunk(
                    id=child_id,
                    document_id=document_id,
                    organization_id=organization_id,
                    parent_chunk_id=parent_id,
                    chunk_index=global_chunk_index,
                    chunk_type=child_item.chunk_type,
                    content=child_item.content,
                    heading_context=child_item.heading_context,
                    heading_path=child_item.heading_path,
                    page_number=child_item.page_number,
                    section=child_item.section,
                    source_locator=child_locator,
                    token_count=child_tokens,
                    character_count=len(child_item.content),
                    content_hash=child_hash,
                    chunker_version=self.config.CHUNKER_VERSION,
                    metadata=dict(child_item.metadata),
                )
                final_chunks.append(child_chunk)
                global_chunk_index += 1

        return final_chunks
