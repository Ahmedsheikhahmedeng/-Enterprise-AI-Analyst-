"""Intelligent, structure-aware document chunking service.

Transforms canonical ParsedDocument instances into validated, deterministic,
multilingual DocumentChunk representations with parent/child relationships,
table header preservation, and heading context tracking.
"""

import uuid
from typing import Any

from app.chunking.boundaries import HeadingPathTracker
from app.chunking.config import ChunkingConfig, default_chunking_config
from app.chunking.hashing import compute_content_hash
from app.chunking.metrics import compute_quality_summary
from app.chunking.models import ChunkQualitySummary, ChunkType, IntermediateChunk, SourceLocator
from app.chunking.parent_child import ParentChildGenerator
from app.chunking.strategies import (
    HugeBlockFallbackStrategy,
    ListChunkingStrategy,
    RawChunkItem,
    TableChunkingStrategy,
)
from app.chunking.tokenizer import TokenCounter, default_token_counter
from app.chunking.validators import validate_chunks
from app.ingestion.models import BlockType, ParsedBlock, ParsedDocument


class ChunkingService:
    """Core domain service for structure-aware document chunking."""

    def __init__(
        self,
        config: ChunkingConfig = default_chunking_config,
        token_counter: TokenCounter = default_token_counter,
    ) -> None:
        self.config = config
        self.token_counter = token_counter
        self.table_strategy = TableChunkingStrategy(config=config, token_counter=token_counter)
        self.list_strategy = ListChunkingStrategy(config=config, token_counter=token_counter)
        self.block_strategy = HugeBlockFallbackStrategy(config=config, token_counter=token_counter)
        self.hierarchy_generator = ParentChildGenerator(config=config, token_counter=token_counter)

    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        organization_id: uuid.UUID,
    ) -> tuple[list[IntermediateChunk], ChunkQualitySummary]:
        """Transform a canonical ParsedDocument into validated chunks + quality summary."""
        raw_items: list[RawChunkItem] = []
        heading_tracker = HeadingPathTracker()

        # Phase 1: Structure analysis and raw item extraction
        if parsed_doc.sections:
            raw_items.extend(
                self._extract_from_sections(
                    sections=parsed_doc.sections,
                    document_id=parsed_doc.document_id,
                    heading_tracker=heading_tracker,
                )
            )
        elif parsed_doc.pages:
            raw_items.extend(
                self._extract_from_pages(
                    pages=parsed_doc.pages,
                    document_id=parsed_doc.document_id,
                    heading_tracker=heading_tracker,
                )
            )

        # Standalone tables (CSV, Excel sheets, or top-level tables)
        if parsed_doc.tables:
            for t_idx, table in enumerate(parsed_doc.tables):
                table_items = self.table_strategy.chunk_table(
                    table=table,
                    document_id=parsed_doc.document_id,
                    heading_path=heading_tracker.heading_path,
                    heading_context=heading_tracker.heading_context,
                    section_title=table.sheet_name or "Tables",
                    table_index=t_idx,
                )
                raw_items.extend(table_items)

        # Fallback for empty or unrecognized document structure with title
        if not raw_items and parsed_doc.title:
            # Check if there is any text in metadata or title
            title_text = parsed_doc.title.strip()
            if title_text:
                raw_items.append(
                    RawChunkItem(
                        content=title_text,
                        chunk_type=ChunkType.TEXT,
                        heading_path=[title_text],
                        heading_context=title_text,
                        source_locator=SourceLocator(document_id=parsed_doc.document_id),
                    )
                )

        # Phase 2: Small chunk merging (e.g. orphan heading or tiny fragment)
        merged_items = self._merge_small_chunks(raw_items)

        # Phase 3: Deduplication (conservative within identical section + page + content)
        deduped_items = self._deduplicate_raw_items(merged_items)

        # Phase 4: Parent / Child hierarchy generation
        chunks = self.hierarchy_generator.build_hierarchy(
            raw_items=deduped_items,
            document_id=parsed_doc.document_id,
            organization_id=organization_id,
        )

        # Phase 5: Quality validation
        validate_chunks(
            chunks=chunks,
            expected_document_id=parsed_doc.document_id,
            expected_organization_id=organization_id,
            config=self.config,
        )

        # Phase 6: Metrics summary
        summary = compute_quality_summary(
            chunks=chunks,
            document_id=parsed_doc.document_id,
            organization_id=organization_id,
            config=self.config,
        )

        return chunks, summary

    def _extract_from_sections(
        self,
        sections: list[Any],
        document_id: uuid.UUID,
        heading_tracker: HeadingPathTracker,
    ) -> list[RawChunkItem]:
        items: list[RawChunkItem] = []
        for sec in sections:
            heading_tracker.update(level=sec.level, title=sec.title)
            for b_idx, block in enumerate(sec.blocks):
                block_id = f"sec_{sec.title}_b_{b_idx}"
                items.extend(
                    self._extract_block(
                        block=block,
                        document_id=document_id,
                        heading_tracker=heading_tracker,
                        section_title=sec.title,
                        page_number=None,
                        block_id=block_id,
                    )
                )
        return items

    def _extract_from_pages(
        self,
        pages: list[Any],
        document_id: uuid.UUID,
        heading_tracker: HeadingPathTracker,
    ) -> list[RawChunkItem]:
        items: list[RawChunkItem] = []
        for page in pages:
            for b_idx, block in enumerate(page.blocks):
                block_id = f"p_{page.page_number}_b_{b_idx}"
                items.extend(
                    self._extract_block(
                        block=block,
                        document_id=document_id,
                        heading_tracker=heading_tracker,
                        section_title=heading_tracker.heading_context or None,
                        page_number=page.page_number,
                        block_id=block_id,
                    )
                )
            for t_idx, table in enumerate(page.tables):
                table_items = self.table_strategy.chunk_table(
                    table=table,
                    document_id=document_id,
                    heading_path=heading_tracker.heading_path,
                    heading_context=heading_tracker.heading_context,
                    section_title=heading_tracker.heading_context or None,
                    table_index=t_idx,
                )
                items.extend(table_items)
        return items

    def _extract_block(
        self,
        block: ParsedBlock,
        document_id: uuid.UUID,
        heading_tracker: HeadingPathTracker,
        section_title: str | None,
        page_number: int | None,
        block_id: str,
    ) -> list[RawChunkItem]:
        text = block.text.strip()
        if not text:
            return []

        if block.type == BlockType.HEADING:
            level = int(block.metadata.get("level", 1)) if block.metadata else 1
            heading_tracker.update(level=level, title=text)
            locator = SourceLocator(
                document_id=document_id,
                page_number=page_number,
                section_title=section_title or text,
                block_id=block_id,
            )
            return [
                RawChunkItem(
                    content=text,
                    chunk_type=ChunkType.HEADING,
                    heading_path=heading_tracker.heading_path,
                    heading_context=heading_tracker.heading_context,
                    page_number=page_number,
                    section=section_title or text,
                    source_locator=locator,
                )
            ]

        if block.type == BlockType.LIST:
            return self.list_strategy.chunk_list(
                block=block,
                document_id=document_id,
                heading_path=heading_tracker.heading_path,
                heading_context=heading_tracker.heading_context,
                page_number=page_number,
                section_title=section_title,
                block_id=block_id,
            )

        # Standard paragraph or other text
        return self.block_strategy.chunk_block(
            text=text,
            chunk_type=ChunkType.PARAGRAPH if block.type == BlockType.PARAGRAPH else ChunkType.TEXT,
            document_id=document_id,
            heading_path=heading_tracker.heading_path,
            heading_context=heading_tracker.heading_context,
            page_number=page_number,
            section_title=section_title,
            block_id=block_id,
        )

    def _merge_small_chunks(self, items: list[RawChunkItem]) -> list[RawChunkItem]:
        """Merge short fragments (e.g. orphan heading) with next item if context is shared."""
        if not items or len(items) <= 1:
            return items

        merged: list[RawChunkItem] = []
        i = 0
        while i < len(items):
            current = items[i]
            current_tokens = self.token_counter.count_tokens(current.content)

            # If current is an orphan heading or tiny fragment, and next item is compatible text
            if (
                current_tokens < self.config.SMALL_CHUNK_THRESHOLD_TOKENS
                and i + 1 < len(items)
                and current.chunk_type in (ChunkType.HEADING, ChunkType.TEXT)
            ):
                next_item = items[i + 1]
                combined_content = f"{current.content}\n\n{next_item.content}"
                combined_tokens = self.token_counter.count_tokens(combined_content)

                if (
                    combined_tokens <= self.config.TARGET_CHUNK_TOKENS
                    and len(combined_content) <= self.config.MAX_CHUNK_CHARACTERS
                    and next_item.chunk_type not in (ChunkType.TABLE,)
                ):
                    # Merge into next item
                    merged.append(
                        RawChunkItem(
                            content=combined_content,
                            chunk_type=ChunkType.COMPOSITE,
                            heading_path=current.heading_path or next_item.heading_path,
                            heading_context=current.heading_context or next_item.heading_context,
                            page_number=current.page_number or next_item.page_number,
                            section=current.section or next_item.section,
                            source_locator=next_item.source_locator or current.source_locator,
                            metadata={
                                "merged_from": [
                                    current.chunk_type.value,
                                    next_item.chunk_type.value,
                                ]
                            },
                        )
                    )
                    i += 2
                    continue

            merged.append(current)
            i += 1

        return merged

    def _deduplicate_raw_items(self, items: list[RawChunkItem]) -> list[RawChunkItem]:
        """Deduplicate items with identical normalized content, heading, and page location."""
        seen: set[tuple[str, str, int | None]] = set()
        deduped: list[RawChunkItem] = []

        for item in items:
            c_hash = compute_content_hash(item.content)
            ctx = item.heading_context or ""
            key = (c_hash, ctx, item.page_number)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)

        return deduped


# Global service instance
default_chunking_service = ChunkingService()
