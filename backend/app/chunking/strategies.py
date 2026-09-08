"""Chunking strategies for text, paragraphs, lists, tables, and fallback splitting.

Respects document structure, heading hierarchy, table schema preservation,
list cohesion, and graceful fallback for oversized blocks.
"""

from typing import Any

from app.chunking.boundaries import SentenceSplitter, default_sentence_splitter
from app.chunking.config import ChunkingConfig, default_chunking_config
from app.chunking.models import ChunkType, SourceLocator
from app.chunking.tokenizer import TokenCounter, default_token_counter
from app.ingestion.models import ParsedBlock, ParsedTable


class RawChunkItem:
    """Internal working structure before final intermediate chunk generation."""

    def __init__(
        self,
        content: str,
        chunk_type: ChunkType,
        heading_path: list[str],
        heading_context: str | None = None,
        page_number: int | None = None,
        section: str | None = None,
        source_locator: SourceLocator | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.content = content.strip()
        self.chunk_type = chunk_type
        self.heading_path = list(heading_path)
        self.heading_context = heading_context
        self.page_number = page_number
        self.section = section
        self.source_locator = source_locator
        self.metadata = metadata or {}


class TableChunkingStrategy:
    """Specialized table chunker preserving header semantics across all row slices."""

    def __init__(
        self,
        config: ChunkingConfig = default_chunking_config,
        token_counter: TokenCounter = default_token_counter,
    ) -> None:
        self.config = config
        self.token_counter = token_counter

    def _render_markdown(self, headers: list[str], rows: list[list[str]]) -> str:
        """Render markdown table string from headers and row list."""
        if not headers and not rows:
            return ""

        col_count = len(headers) if headers else (max(len(r) for r in rows) if rows else 0)
        norm_headers = [h.replace("\n", " ").replace("|", "\\|").strip() for h in headers]
        if not norm_headers and col_count > 0:
            norm_headers = [f"Col {i + 1}" for i in range(col_count)]

        # Header row
        header_line = "| " + " | ".join(norm_headers) + " |"
        sep_line = "| " + " | ".join(["---"] * len(norm_headers)) + " |"

        # Row lines
        row_lines: list[str] = []
        for r in rows:
            padded_row = [
                (r[i].replace("\n", " ").replace("|", "\\|").strip() if i < len(r) else "")
                for i in range(len(norm_headers))
            ]
            row_lines.append("| " + " | ".join(padded_row) + " |")

        return "\n".join([header_line, sep_line] + row_lines)

    def chunk_table(
        self,
        table: ParsedTable,
        document_id: Any,
        heading_path: list[str],
        heading_context: str | None = None,
        section_title: str | None = None,
        table_index: int = 0,
    ) -> list[RawChunkItem]:
        """Convert a ParsedTable into one or more structure-preserving table chunks."""
        headers = table.headers
        rows = table.rows
        total_rows = len(rows)

        if not headers and not rows:
            return []

        # Check if full table fits within token & character limits
        full_md = self._render_markdown(headers, rows)
        full_tokens = self.token_counter.count_tokens(full_md)

        if (
            full_tokens <= self.config.TARGET_CHUNK_TOKENS
            and len(full_md) <= self.config.MAX_CHUNK_CHARACTERS
            and len(rows) <= self.config.MAX_TABLE_ROWS_PER_SLICE
        ):
            locator = SourceLocator(
                document_id=document_id,
                page_number=table.page_number,
                section_title=section_title,
                table_id=f"table_{table_index}",
                sheet_name=table.sheet_name,
                row_start=0,
                row_end=total_rows,
            )
            return [
                RawChunkItem(
                    content=full_md,
                    chunk_type=ChunkType.TABLE,
                    heading_path=heading_path,
                    heading_context=heading_context,
                    page_number=table.page_number,
                    section=section_title,
                    source_locator=locator,
                    metadata={
                        "row_start": 0,
                        "row_end": total_rows,
                        "total_rows": total_rows,
                        "sheet_name": table.sheet_name,
                    },
                )
            ]

        # Table exceeds limits: slice rows deterministically, replicating headers on EVERY slice
        chunks: list[RawChunkItem] = []
        current_rows: list[list[str]] = []
        slice_start = 0

        for r_idx, row in enumerate(rows):
            test_rows = current_rows + [row]
            test_md = self._render_markdown(headers, test_rows)
            test_tokens = self.token_counter.count_tokens(test_md)

            # If adding row exceeds target tokens or row count limit (and current_rows not empty)
            if current_rows and (
                test_tokens > self.config.TARGET_CHUNK_TOKENS
                or len(test_md) > self.config.MAX_CHUNK_CHARACTERS
                or len(current_rows) >= self.config.MAX_TABLE_ROWS_PER_SLICE
            ):
                slice_md = self._render_markdown(headers, current_rows)
                locator = SourceLocator(
                    document_id=document_id,
                    page_number=table.page_number,
                    section_title=section_title,
                    table_id=f"table_{table_index}",
                    sheet_name=table.sheet_name,
                    row_start=slice_start,
                    row_end=r_idx,
                )
                chunks.append(
                    RawChunkItem(
                        content=slice_md,
                        chunk_type=ChunkType.TABLE,
                        heading_path=heading_path,
                        heading_context=heading_context,
                        page_number=table.page_number,
                        section=section_title,
                        source_locator=locator,
                        metadata={
                            "row_start": slice_start,
                            "row_end": r_idx,
                            "total_rows": total_rows,
                            "sheet_name": table.sheet_name,
                        },
                    )
                )
                current_rows = [row]
                slice_start = r_idx
            else:
                current_rows.append(row)

        if current_rows:
            slice_md = self._render_markdown(headers, current_rows)
            locator = SourceLocator(
                document_id=document_id,
                page_number=table.page_number,
                section_title=section_title,
                table_id=f"table_{table_index}",
                sheet_name=table.sheet_name,
                row_start=slice_start,
                row_end=total_rows,
            )
            chunks.append(
                RawChunkItem(
                    content=slice_md,
                    chunk_type=ChunkType.TABLE,
                    heading_path=heading_path,
                    heading_context=heading_context,
                    page_number=table.page_number,
                    section=section_title,
                    source_locator=locator,
                    metadata={
                        "row_start": slice_start,
                        "row_end": total_rows,
                        "total_rows": total_rows,
                        "sheet_name": table.sheet_name,
                    },
                )
            )

        return chunks


class ListChunkingStrategy:
    """Specialized list chunker keeping list items cohesive without breaking mid-item."""

    def __init__(
        self,
        config: ChunkingConfig = default_chunking_config,
        token_counter: TokenCounter = default_token_counter,
    ) -> None:
        self.config = config
        self.token_counter = token_counter

    def chunk_list(
        self,
        block: ParsedBlock,
        document_id: Any,
        heading_path: list[str],
        heading_context: str | None = None,
        page_number: int | None = None,
        section_title: str | None = None,
        block_id: str | None = None,
    ) -> list[RawChunkItem]:
        """Chunk a list block respecting item boundaries."""
        text = block.text.strip()
        if not text:
            return []

        tokens = self.token_counter.count_tokens(text)
        if (
            tokens <= self.config.TARGET_CHUNK_TOKENS
            and len(text) <= self.config.MAX_CHUNK_CHARACTERS
        ):
            locator = SourceLocator(
                document_id=document_id,
                page_number=page_number,
                section_title=section_title,
                block_id=block_id,
            )
            return [
                RawChunkItem(
                    content=text,
                    chunk_type=ChunkType.LIST,
                    heading_path=heading_path,
                    heading_context=heading_context,
                    page_number=page_number,
                    section=section_title,
                    source_locator=locator,
                )
            ]

        # List exceeds max tokens: split by lines/items
        items = [line for line in text.split("\n") if line.strip()]
        chunks: list[RawChunkItem] = []
        current_items: list[str] = []

        for item in items:
            test_items = current_items + [item]
            test_text = "\n".join(test_items)
            test_tokens = self.token_counter.count_tokens(test_text)

            if current_items and (
                test_tokens > self.config.TARGET_CHUNK_TOKENS
                or len(test_text) > self.config.MAX_CHUNK_CHARACTERS
            ):
                content = "\n".join(current_items)
                locator = SourceLocator(
                    document_id=document_id,
                    page_number=page_number,
                    section_title=section_title,
                    block_id=block_id,
                )
                chunks.append(
                    RawChunkItem(
                        content=content,
                        chunk_type=ChunkType.LIST,
                        heading_path=heading_path,
                        heading_context=heading_context,
                        page_number=page_number,
                        section=section_title,
                        source_locator=locator,
                    )
                )
                current_items = [item]
            else:
                current_items.append(item)

        if current_items:
            content = "\n".join(current_items)
            locator = SourceLocator(
                document_id=document_id,
                page_number=page_number,
                section_title=section_title,
                block_id=block_id,
            )
            chunks.append(
                RawChunkItem(
                    content=content,
                    chunk_type=ChunkType.LIST,
                    heading_path=heading_path,
                    heading_context=heading_context,
                    page_number=page_number,
                    section=section_title,
                    source_locator=locator,
                )
            )

        return chunks


class HugeBlockFallbackStrategy:
    """Cascading fallback splitter for large or continuous blocks.

    Pipeline:
    1. Paragraph splitting (\n\n)
    2. Sentence splitting
    3. Token/Character hard bounded windowing (for 50,000-char continuous text)
    """

    def __init__(
        self,
        config: ChunkingConfig = default_chunking_config,
        token_counter: TokenCounter = default_token_counter,
        sentence_splitter: SentenceSplitter = default_sentence_splitter,
    ) -> None:
        self.config = config
        self.token_counter = token_counter
        self.sentence_splitter = sentence_splitter

    def chunk_block(
        self,
        text: str,
        chunk_type: ChunkType,
        document_id: Any,
        heading_path: list[str],
        heading_context: str | None = None,
        page_number: int | None = None,
        section_title: str | None = None,
        block_id: str | None = None,
    ) -> list[RawChunkItem]:
        """Split block into bounded chunks respecting sentence boundaries and limits."""
        text = text.strip()
        if not text:
            return []

        tokens = self.token_counter.count_tokens(text)
        if tokens <= self.config.MAX_CHUNK_TOKENS and len(text) <= self.config.MAX_CHUNK_CHARACTERS:
            locator = SourceLocator(
                document_id=document_id,
                page_number=page_number,
                section_title=section_title,
                block_id=block_id,
            )
            return [
                RawChunkItem(
                    content=text,
                    chunk_type=chunk_type,
                    heading_path=heading_path,
                    heading_context=heading_context,
                    page_number=page_number,
                    section=section_title,
                    source_locator=locator,
                )
            ]

        # Step 1: Split into paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) > 1:
            raw_items: list[RawChunkItem] = []
            for p in paragraphs:
                raw_items.extend(
                    self.chunk_block(
                        p,
                        chunk_type,
                        document_id,
                        heading_path,
                        heading_context,
                        page_number,
                        section_title,
                        block_id,
                    )
                )
            return raw_items

        # Step 2: Split single large paragraph into sentences
        sentences = self.sentence_splitter.split(text)
        chunks: list[RawChunkItem] = []
        current_sentences: list[str] = []

        for sent in sentences:
            sent_tokens = self.token_counter.count_tokens(sent)

            # If a single sentence exceeds MAX_CHUNK_TOKENS, fallback to token slicing
            if (
                sent_tokens > self.config.MAX_CHUNK_TOKENS
                or len(sent) > self.config.MAX_CHUNK_CHARACTERS
            ):
                # Flush accumulated sentences first
                if current_sentences:
                    content = " ".join(current_sentences)
                    locator = SourceLocator(
                        document_id=document_id,
                        page_number=page_number,
                        section_title=section_title,
                        block_id=block_id,
                    )
                    chunks.append(
                        RawChunkItem(
                            content=content,
                            chunk_type=chunk_type,
                            heading_path=heading_path,
                            heading_context=heading_context,
                            page_number=page_number,
                            section=section_title,
                            source_locator=locator,
                        )
                    )
                    current_sentences = []

                # Fallback to token bounded segments
                sub_segments = self._split_huge_sentence(sent)
                for seg in sub_segments:
                    locator = SourceLocator(
                        document_id=document_id,
                        page_number=page_number,
                        section_title=section_title,
                        block_id=block_id,
                    )
                    chunks.append(
                        RawChunkItem(
                            content=seg,
                            chunk_type=chunk_type,
                            heading_path=heading_path,
                            heading_context=heading_context,
                            page_number=page_number,
                            section=section_title,
                            source_locator=locator,
                        )
                    )
                continue

            # Standard accumulation with TARGET_CHUNK_TOKENS
            test_sentences = current_sentences + [sent]
            test_text = " ".join(test_sentences)
            test_tokens = self.token_counter.count_tokens(test_text)

            if current_sentences and (
                test_tokens > self.config.TARGET_CHUNK_TOKENS
                or len(test_text) > self.config.MAX_CHUNK_CHARACTERS
            ):
                content = " ".join(current_sentences)
                locator = SourceLocator(
                    document_id=document_id,
                    page_number=page_number,
                    section_title=section_title,
                    block_id=block_id,
                )
                chunks.append(
                    RawChunkItem(
                        content=content,
                        chunk_type=chunk_type,
                        heading_path=heading_path,
                        heading_context=heading_context,
                        page_number=page_number,
                        section=section_title,
                        source_locator=locator,
                    )
                )
                current_sentences = [sent]
            else:
                current_sentences.append(sent)

        if current_sentences:
            content = " ".join(current_sentences)
            locator = SourceLocator(
                document_id=document_id,
                page_number=page_number,
                section_title=section_title,
                block_id=block_id,
            )
            chunks.append(
                RawChunkItem(
                    content=content,
                    chunk_type=chunk_type,
                    heading_path=heading_path,
                    heading_context=heading_context,
                    page_number=page_number,
                    section=section_title,
                    source_locator=locator,
                )
            )

        return chunks

    def _split_huge_sentence(self, sentence: str) -> list[str]:
        """Deterministic windowed split of an oversized sentence by tokens."""
        raw_tokens = self.token_counter.split_into_tokens(sentence)
        max_char = self.config.MAX_CHUNK_CHARACTERS

        # If any individual token exceeds MAX_CHUNK_CHARACTERS, slice it into bounded pieces
        tokens: list[str] = []
        for r_tok in raw_tokens:
            if len(r_tok) > max_char:
                for i in range(0, len(r_tok), max_char):
                    tokens.append(r_tok[i : i + max_char])
            else:
                tokens.append(r_tok)

        segments: list[str] = []
        current_tokens: list[str] = []
        current_count = 0

        for tok in tokens:
            if not tok.isspace():
                tok_len = len(tok)
                sub_count = 1 + ((tok_len - 8) // 4 if tok_len > 8 else 0)
            else:
                sub_count = 0

            test_text = "".join(current_tokens + [tok])
            if current_tokens and (
                current_count + sub_count > self.config.TARGET_CHUNK_TOKENS
                or len(test_text) > self.config.MAX_CHUNK_CHARACTERS
            ):
                seg = "".join(current_tokens).strip()
                if seg:
                    segments.append(seg)
                current_tokens = [tok]
                current_count = sub_count
            else:
                current_tokens.append(tok)
                current_count += sub_count

        if current_tokens:
            seg = "".join(current_tokens).strip()
            if seg:
                segments.append(seg)

        return segments
