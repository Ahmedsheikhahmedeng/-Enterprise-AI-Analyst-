"""Plain text parser supporting UTF-8 and multilingual content."""

import re
import uuid
from typing import Any

from app.ingestion.exceptions import ParsingError, ResourceLimitExceededError
from app.ingestion.models import (
    BlockType,
    IngestionLimits,
    ParsedBlock,
    ParsedDocument,
    ParsedSection,
)
from app.ingestion.parsers.base import DocumentParser


class TXTParser(DocumentParser):
    """Parser for plain text documents."""

    parser_name: str = "builtin-txt"
    parser_version: str = "1.0.0"
    supported_mime_types: set[str] = {
        "text/plain",
        "text/markdown",
    }

    def parse(
        self,
        file_bytes: bytes,
        document_id: uuid.UUID,
        filename: str,
        limits: IngestionLimits,
    ) -> ParsedDocument:
        # Check UTF-8 decoding
        try:
            # First try standard UTF-8 (handling optional BOM via utf-8-sig)
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParsingError(
                f"Text file decoding error: {exc}",
                safe_reason="File is not valid UTF-8 encoded text.",
            ) from exc

        if len(text) > limits.max_characters:
            raise ResourceLimitExceededError(
                f"TXT exceeds character limit ({len(text)} > {limits.max_characters}).",
                safe_reason=(
                    f"Document exceeds maximum character extraction ceiling "
                    f"of {limits.max_characters}."
                ),
            )

        # Standardize newlines
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split into paragraphs based on 2 or more newlines
        raw_paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

        blocks: list[ParsedBlock] = []
        for p in raw_paragraphs:
            # Check if paragraph looks like a markdown heading or title
            if p.startswith("#"):
                match = re.match(r"^(#+)\s*(.+)$", p)
                if match:
                    level = len(match.group(1))
                    heading_text = match.group(2).strip()
                    blocks.append(
                        ParsedBlock(
                            type=BlockType.HEADING,
                            text=heading_text,
                            metadata={"level": level},
                        )
                    )
                    continue

            # Check if list block
            lines = p.split("\n")
            is_list = len(lines) > 1 and all(
                re.match(r"^(\d+[\.\)]|[\-\*•])\s+", line_item.strip())
                for line_item in lines
                if line_item.strip()
            )
            if is_list:
                blocks.append(
                    ParsedBlock(
                        type=BlockType.LIST,
                        text=p,
                        metadata={"item_count": len(lines)},
                    )
                )
            else:
                blocks.append(
                    ParsedBlock(
                        type=BlockType.PARAGRAPH,
                        text=p,
                        metadata={},
                    )
                )

        section = ParsedSection(
            title="Content",
            level=1,
            blocks=blocks,
        )

        metadata: dict[str, Any] = {
            "paragraph_count": len(blocks),
            "character_count": len(text),
            "encoding": "utf-8",
        }

        return ParsedDocument(
            document_id=document_id,
            title=filename,
            source_type="txt",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            pages=[],
            sections=[section],
            tables=[],
            metadata=metadata,
        )
