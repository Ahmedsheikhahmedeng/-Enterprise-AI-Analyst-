"""Text and structural normalization layer for canonical parsed documents."""

import re
import unicodedata

from app.ingestion.models import (
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
    ParsedSection,
    ParsedTable,
)

# Regex to remove non-printable ASCII/Unicode control characters except newline and tab
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
# Regex to normalize multiple consecutive horizontal spaces/tabs (preserving newlines)
_HORIZONTAL_WHITESPACE_RE = re.compile(r"[^\S\n\r]+")
# Regex to normalize multiple consecutive newlines to at most two
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Normalize text while preserving multilingual characters, punctuation, and structure.

    Operations:
    1. Line ending normalization (\\r\\n, \\r -> \\n)
    2. Unicode NFC normalization (preserves Arabic, Turkish, diacritics, currencies)
    3. Removal of non-printable control characters (except \\n and \\t)
    4. Collapse of multiple horizontal spaces into single spaces
    5. Clean line-by-line whitespace
    6. Collapse excessive blank lines (max 2 consecutive newlines)
    """
    if not text:
        return ""

    # 1. Standardize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Unicode Normalization Form C (canonical decomposition followed by canonical composition)
    text = unicodedata.normalize("NFC", text)

    # 3. Strip dangerous control characters
    text = _CONTROL_CHAR_RE.sub("", text)

    # 4. Normalize line by line
    lines = text.split("\n")
    normalized_lines: list[str] = []
    for line in lines:
        cleaned_line = _HORIZONTAL_WHITESPACE_RE.sub(" ", line).strip()
        normalized_lines.append(cleaned_line)

    text = "\n".join(normalized_lines)

    # 5. Collapse excessive vertical blank space (keep max two newlines for paragraph separation)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)

    return text.strip()


def normalize_block(block: ParsedBlock) -> ParsedBlock:
    """Normalize a single parsed block."""
    norm_text = normalize_text(block.text)
    return ParsedBlock(
        type=block.type,
        text=norm_text,
        metadata=dict(block.metadata),
    )


def normalize_table(table: ParsedTable) -> ParsedTable:
    """Normalize tabular headers and cell contents."""
    norm_headers = [normalize_text(h) for h in table.headers]
    norm_rows = [[normalize_text(cell) for cell in row] for row in table.rows]
    return ParsedTable(
        headers=norm_headers,
        rows=norm_rows,
        page_number=table.page_number,
        sheet_name=table.sheet_name,
        metadata=dict(table.metadata),
    )


def normalize_page(page: ParsedPage) -> ParsedPage:
    """Normalize blocks and tables within a page."""
    norm_blocks = [normalize_block(b) for b in page.blocks if normalize_text(b.text)]
    norm_tables = [normalize_table(t) for t in page.tables]
    return ParsedPage(
        page_number=page.page_number,
        blocks=norm_blocks,
        tables=norm_tables,
        metadata=dict(page.metadata),
    )


def normalize_section(section: ParsedSection) -> ParsedSection:
    """Normalize a document section and its constituent blocks."""
    norm_title = normalize_text(section.title)
    norm_blocks = [normalize_block(b) for b in section.blocks if normalize_text(b.text)]
    return ParsedSection(
        title=norm_title,
        level=section.level,
        blocks=norm_blocks,
    )


def normalize_document(doc: ParsedDocument) -> ParsedDocument:
    """Normalize entire canonical document tree."""
    norm_title = normalize_text(doc.title)
    norm_pages = [normalize_page(p) for p in doc.pages]
    norm_sections = [normalize_section(s) for s in doc.sections]
    norm_tables = [normalize_table(t) for t in doc.tables]

    # Compute updated metadata statistics after normalization
    metadata = dict(doc.metadata)
    metadata["normalized"] = True
    metadata["total_pages"] = len(norm_pages)
    metadata["total_sections"] = len(norm_sections)
    metadata["total_tables"] = len(norm_tables)

    normalized_doc = ParsedDocument(
        document_id=doc.document_id,
        title=norm_title,
        source_type=doc.source_type,
        parser_name=doc.parser_name,
        parser_version=doc.parser_version,
        pages=norm_pages,
        sections=norm_sections,
        tables=norm_tables,
        metadata=metadata,
    )

    metadata["character_count"] = normalized_doc.total_character_count
    metadata["word_count"] = normalized_doc.total_word_count

    return normalized_doc
