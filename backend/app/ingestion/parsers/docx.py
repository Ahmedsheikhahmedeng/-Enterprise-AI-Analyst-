"""DOCX document parser preserving document element order, headings, and tables."""

import io
import re
import uuid
from typing import Any

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.ingestion.exceptions import ParsingError, ResourceLimitExceededError
from app.ingestion.models import (
    BlockType,
    IngestionLimits,
    ParsedBlock,
    ParsedDocument,
    ParsedSection,
    ParsedTable,
)
from app.ingestion.parsers.base import DocumentParser

_HEADING_NUM_RE = re.compile(r"Heading\s*(\d+)", re.IGNORECASE)


class DOCXParser(DocumentParser):
    """Parser for Microsoft Word (.docx) documents."""

    parser_name: str = "python-docx"
    parser_version: str = "1.2.0"
    supported_mime_types: set[str] = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }

    def parse(
        self,
        file_bytes: bytes,
        document_id: uuid.UUID,
        filename: str,
        limits: IngestionLimits,
    ) -> ParsedDocument:
        try:
            doc = docx.Document(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ParsingError(f"Corrupted or invalid DOCX document: {exc}") from exc

        sections: list[ParsedSection] = []
        current_section = ParsedSection(title="Introduction", level=1, blocks=[])
        tables: list[ParsedTable] = []
        cumulative_characters = 0

        # Iterate body children to preserve exact document ordering
        for child in doc.element.body:
            if child.tag.endswith("p"):
                para = Paragraph(child, doc)
                text = para.text.strip()
                if not text:
                    continue

                cumulative_characters += len(text)
                if cumulative_characters > limits.max_characters:
                    raise ResourceLimitExceededError(
                        f"DOCX exceeds character limit "
                        f"({cumulative_characters} > {limits.max_characters}).",
                        safe_reason=(
                            f"Document exceeds maximum character extraction ceiling "
                            f"of {limits.max_characters}."
                        ),
                    )

                style_name = para.style.name if para.style else "Normal"

                # Check if heading
                if "Heading" in style_name or style_name.lower() == "title":
                    level = 1
                    match = _HEADING_NUM_RE.search(style_name)
                    if match:
                        level = int(match.group(1))

                    block = ParsedBlock(
                        type=BlockType.HEADING,
                        text=text,
                        metadata={"style": style_name, "level": level},
                    )

                    # If current section has blocks, finalize it and start a new section
                    if current_section.blocks:
                        sections.append(current_section)
                    current_section = ParsedSection(title=text, level=level, blocks=[block])

                elif "List" in style_name or re.match(r"^(\d+[\.\)]|[\-\*•])\s+", text):
                    block = ParsedBlock(
                        type=BlockType.LIST,
                        text=text,
                        metadata={"style": style_name},
                    )
                    current_section.blocks.append(block)
                else:
                    block = ParsedBlock(
                        type=BlockType.PARAGRAPH,
                        text=text,
                        metadata={"style": style_name},
                    )
                    current_section.blocks.append(block)

            elif child.tag.endswith("tbl"):
                table = Table(child, doc)
                if not table.rows:
                    continue

                headers: list[str] = [cell.text.strip() for cell in table.rows[0].cells]
                data_rows: list[list[str]] = []
                for row in table.rows[1:]:
                    data_rows.append([cell.text.strip() for cell in row.cells])

                table_chars = sum(len(h) for h in headers) + sum(
                    len(c) for r in data_rows for c in r
                )
                cumulative_characters += table_chars
                if cumulative_characters > limits.max_characters:
                    raise ResourceLimitExceededError(
                        f"DOCX exceeds character limit "
                        f"({cumulative_characters} > {limits.max_characters}).",
                        safe_reason=(
                            f"Document exceeds maximum character extraction ceiling "
                            f"of {limits.max_characters}."
                        ),
                    )

                parsed_table = ParsedTable(
                    headers=headers,
                    rows=data_rows,
                    metadata={"source": "docx_table"},
                )
                tables.append(parsed_table)

                # Also insert table representation block in current section
                # to preserve sequential order
                table_text = "\n".join(["\t".join(headers)] + ["\t".join(r) for r in data_rows])
                current_section.blocks.append(
                    ParsedBlock(
                        type=BlockType.TABLE,
                        text=table_text,
                        metadata={"table_index": len(tables) - 1},
                    )
                )

        if current_section.blocks:
            sections.append(current_section)

        metadata: dict[str, Any] = {
            "section_count": len(sections),
            "table_count": len(tables),
            "character_count": cumulative_characters,
        }

        # Safe metadata extraction from core properties
        try:
            core = doc.core_properties
            if core.title:
                metadata["title"] = core.title
            if core.author:
                metadata["author"] = core.author
            if core.created:
                metadata["created_at"] = core.created.isoformat()
            if core.modified:
                metadata["modified_at"] = core.modified.isoformat()
        except Exception:
            pass

        return ParsedDocument(
            document_id=document_id,
            title=filename,
            source_type="docx",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            pages=[],
            sections=sections,
            tables=tables,
            metadata=metadata,
        )
