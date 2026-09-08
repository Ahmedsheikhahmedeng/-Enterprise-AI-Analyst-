"""Canonical parsed document representation and domain models for ingestion."""

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BlockType(StrEnum):
    """Semantic block classification for parsed elements."""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    OTHER = "other"


class ParsedBlock(BaseModel):
    """Atomic content unit preserving ordering and classification."""

    model_config = ConfigDict(frozen=True)

    type: BlockType = Field(..., description="Semantic classification of the block")
    text: str = Field(..., description="Normalized text payload")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Block-level metadata such as heading level or coordinates",
    )


class ParsedTable(BaseModel):
    """Tabular structure preserving headers and row-column relationships."""

    model_config = ConfigDict(frozen=True)

    headers: list[str] = Field(default_factory=list, description="Column header labels")
    rows: list[list[str]] = Field(
        default_factory=list,
        description="Ordered grid of cell values formatted as strings",
    )
    page_number: int | None = Field(
        default=None,
        description="Page number where table occurs if applicable",
    )
    sheet_name: str | None = Field(default=None, description="Workbook sheet name if applicable")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Table-level metadata")

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def col_count(self) -> int:
        if self.headers:
            return len(self.headers)
        if self.rows:
            return max(len(r) for r in self.rows)
        return 0


class ParsedPage(BaseModel):
    """Preserves physical page boundaries for paginated documents."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(..., description="1-indexed physical page number")
    blocks: list[ParsedBlock] = Field(
        default_factory=list,
        description="Extracted ordered text blocks on this page",
    )
    tables: list[ParsedTable] = Field(
        default_factory=list,
        description="Extracted tables on this page",
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="Page-level metadata")


class ParsedSection(BaseModel):
    """Hierarchical section grouping for structured documents."""

    model_config = ConfigDict(frozen=True)

    title: str = Field(..., description="Section title or heading")
    level: int = Field(default=1, description="Heading hierarchy level (1, 2, 3...)")
    blocks: list[ParsedBlock] = Field(
        default_factory=list,
        description="Blocks belonging to this section",
    )


class ParsedDocument(BaseModel):
    """Canonical, normalized intermediate representation ready for chunking."""

    model_config = ConfigDict(frozen=True)

    document_id: uuid.UUID = Field(..., description="UUID of the parent document")
    title: str = Field(..., description="Document title or sanitized filename")
    source_type: str = Field(
        ...,
        description="Normalized document type (pdf, docx, txt, csv, xlsx)",
    )
    parser_name: str = Field(..., description="Name of the parsing engine used")
    parser_version: str = Field(..., description="Semantic version of parser")
    pages: list[ParsedPage] = Field(
        default_factory=list,
        description="Pages preserving physical boundaries (PDF, paginated formats)",
    )
    sections: list[ParsedSection] = Field(
        default_factory=list,
        description="Logical document sections (DOCX, structured text)",
    )
    tables: list[ParsedTable] = Field(
        default_factory=list,
        description="All extracted structured tables across the document",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document-level statistics, counts, and extraction metadata",
    )

    @property
    def total_character_count(self) -> int:
        """Calculate total characters across blocks and tables."""
        char_count = 0
        for page in self.pages:
            for block in page.blocks:
                char_count += len(block.text)
        for section in self.sections:
            for block in section.blocks:
                char_count += len(block.text)
        for table in self.tables:
            for h in table.headers:
                char_count += len(h)
            for row in table.rows:
                for cell in row:
                    char_count += len(cell)
        return char_count

    @property
    def total_word_count(self) -> int:
        """Calculate total word count across blocks."""
        words = 0
        for page in self.pages:
            for block in page.blocks:
                words += len(block.text.split())
        for section in self.sections:
            for block in section.blocks:
                words += len(block.text.split())
        return words


class IngestionLimits(BaseModel):
    """Configurable resource and complexity thresholds for parsing."""

    model_config = ConfigDict(frozen=True)

    max_pages: int = Field(
        default=500,
        description="Maximum allowable pages in paginated documents",
    )
    max_rows: int = Field(default=50000, description="Maximum allowable rows in tabular documents")
    max_sheets: int = Field(default=20, description="Maximum allowable sheets in workbooks")
    max_characters: int = Field(
        default=5_000_000,
        description="Maximum cumulative character extraction ceiling",
    )
