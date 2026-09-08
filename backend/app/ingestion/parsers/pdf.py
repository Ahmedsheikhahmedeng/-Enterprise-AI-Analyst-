"""PDF document parser using pypdf."""

import io
import re
import uuid
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.exceptions import ParsingError, ResourceLimitExceededError
from app.ingestion.models import (
    BlockType,
    IngestionLimits,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
    ParsedTable,
)
from app.ingestion.parsers.base import DocumentParser

_TABLE_PIPE_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_MULTI_SPACE_COL_RE = re.compile(r"\s{2,}|\t+")


def _try_extract_table_from_lines(lines: list[str]) -> ParsedTable | None:
    """Attempt to detect structured tabular lines (pipe-delimited or multi-column aligned)."""
    if len(lines) < 2:
        return None

    # Check for markdown/pipe formatted table: | col1 | col2 |
    pipe_rows: list[list[str]] = []
    for line in lines:
        match = _TABLE_PIPE_RE.match(line)
        if match:
            cols = [c.strip() for c in match.group(1).split("|")]
            # Skip separator line like |---|---|
            if all(set(c).issubset({"-", ":", " "}) for c in cols):
                continue
            pipe_rows.append(cols)
        else:
            break

    if len(pipe_rows) >= 2 and len(pipe_rows) == len(lines):
        headers = pipe_rows[0]
        data_rows = pipe_rows[1:]
        return ParsedTable(headers=headers, rows=data_rows)

    # Check for whitespace column aligned table (min 2 rows, consistent column count >= 2)
    parsed_rows: list[list[str]] = []
    col_counts: list[int] = []
    for line in lines:
        cols = [c.strip() for c in _MULTI_SPACE_COL_RE.split(line.strip()) if c.strip()]
        if len(cols) >= 2:
            parsed_rows.append(cols)
            col_counts.append(len(cols))
        else:
            break

    # If all candidate lines have identical column count >= 2 and at least 2 rows
    if len(parsed_rows) >= 2 and len(parsed_rows) == len(lines) and len(set(col_counts)) == 1:
        headers = parsed_rows[0]
        data_rows = parsed_rows[1:]
        return ParsedTable(headers=headers, rows=data_rows)

    return None


class PDFParser(DocumentParser):
    """Parser for PDF files preserving page boundaries and tabular content."""

    parser_name: str = "pypdf"
    parser_version: str = "6.17.0"
    supported_mime_types: set[str] = {
        "application/pdf",
        "application/x-pdf",
    }

    def parse(
        self,
        file_bytes: bytes,
        document_id: uuid.UUID,
        filename: str,
        limits: IngestionLimits,
    ) -> ParsedDocument:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except (PdfReadError, Exception) as exc:
            raise ParsingError(f"Corrupted or unreadable PDF: {exc}") from exc

        if reader.is_encrypted:
            try:
                # Try decrypting with empty password
                if not reader.decrypt(""):
                    raise ParsingError("Encrypted PDF requires a password.")
            except Exception as exc:
                raise ParsingError(f"Cannot decrypt PDF: {exc}") from exc

        num_pages = len(reader.pages)
        if num_pages > limits.max_pages:
            raise ResourceLimitExceededError(
                f"PDF exceeds maximum page limit ({num_pages} > {limits.max_pages}).",
                safe_reason=(
                    f"Document exceeds maximum allowable page limit of {limits.max_pages}."
                ),
            )

        # Extract bookmark headings if available
        outline_titles: set[str] = set()
        try:

            def extract_outline(outline_items: list[Any]) -> None:
                for item in outline_items:
                    if isinstance(item, list):
                        extract_outline(item)
                    elif hasattr(item, "title") and item.title:
                        outline_titles.add(item.title.strip())

            if reader.outline:
                extract_outline(reader.outline)
        except Exception:
            outline_titles = set()

        pages: list[ParsedPage] = []
        all_tables: list[ParsedTable] = []
        cumulative_characters = 0

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                raise ParsingError(f"Error extracting text from page {page_num}: {exc}") from exc

            cumulative_characters += len(page_text)
            if cumulative_characters > limits.max_characters:
                raise ResourceLimitExceededError(
                    f"PDF exceeds maximum character limit "
                    f"({cumulative_characters} > {limits.max_characters}).",
                    safe_reason=(
                        f"Document exceeds maximum character extraction ceiling "
                        f"of {limits.max_characters}."
                    ),
                )

            blocks: list[ParsedBlock] = []
            page_tables: list[ParsedTable] = []

            # Split raw page text into raw paragraphs / sections separated by double newlines
            raw_chunks = [c.strip() for c in page_text.split("\n\n") if c.strip()]

            for chunk in raw_chunks:
                lines = [line.strip() for line in chunk.split("\n") if line.strip()]
                if not lines:
                    continue

                # Check if chunk represents a structured table
                candidate_table = _try_extract_table_from_lines(lines)
                if candidate_table is not None:
                    table_with_page = ParsedTable(
                        headers=candidate_table.headers,
                        rows=candidate_table.rows,
                        page_number=page_num,
                        metadata={"detected_by": "alignment_heuristic"},
                    )
                    page_tables.append(table_with_page)
                    all_tables.append(table_with_page)
                    table_block_text = "\n".join(
                        ["\t".join(table_with_page.headers)]
                        + ["\t".join(r) for r in table_with_page.rows]
                    )
                    blocks.append(
                        ParsedBlock(
                            type=BlockType.TABLE,
                            text=table_block_text,
                            metadata={"table_page": page_num},
                        )
                    )
                    continue

                # Check if chunk is a heading verified by PDF outline or reliable short bookmark
                if len(lines) == 1 and (lines[0] in outline_titles):
                    blocks.append(
                        ParsedBlock(
                            type=BlockType.HEADING,
                            text=lines[0],
                            metadata={"page_number": page_num, "level": 1},
                        )
                    )
                else:
                    # Check list markers (e.g. bullets or numbers: 1., -, *)
                    if all(re.match(r"^(\d+[\.\)]|[\-\*•])\s+", line_item) for line_item in lines):
                        blocks.append(
                            ParsedBlock(
                                type=BlockType.LIST,
                                text="\n".join(lines),
                                metadata={"page_number": page_num},
                            )
                        )
                    else:
                        blocks.append(
                            ParsedBlock(
                                type=BlockType.PARAGRAPH,
                                text="\n".join(lines),
                                metadata={"page_number": page_num},
                            )
                        )

            pages.append(
                ParsedPage(
                    page_number=page_num,
                    blocks=blocks,
                    tables=page_tables,
                    metadata={"character_count": len(page_text)},
                )
            )

        metadata: dict[str, Any] = {
            "page_count": num_pages,
            "table_count": len(all_tables),
            "character_count": cumulative_characters,
        }

        # Add PDF document info if available
        if reader.metadata:
            if reader.metadata.title:
                metadata["pdf_title"] = str(reader.metadata.title)
            if reader.metadata.author:
                metadata["pdf_author"] = str(reader.metadata.author)

        return ParsedDocument(
            document_id=document_id,
            title=filename,
            source_type="pdf",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            pages=pages,
            sections=[],
            tables=all_tables,
            metadata=metadata,
        )
