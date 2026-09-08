"""Structured CSV parser preserving tabular grid, columns, and rows."""

import csv
import io
import uuid
from typing import Any

from app.ingestion.exceptions import ParsingError, ResourceLimitExceededError
from app.ingestion.models import (
    IngestionLimits,
    ParsedDocument,
    ParsedTable,
)
from app.ingestion.parsers.base import DocumentParser


class CSVParser(DocumentParser):
    """Parser for comma/semicolon/tab-separated tabular data."""

    parser_name: str = "builtin-csv"
    parser_version: str = "1.0.0"
    supported_mime_types: set[str] = {
        "text/csv",
        "application/csv",
        "text/comma-separated-values",
    }

    def parse(
        self,
        file_bytes: bytes,
        document_id: uuid.UUID,
        filename: str,
        limits: IngestionLimits,
    ) -> ParsedDocument:
        try:
            text = file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParsingError(
                f"CSV file decoding error: {exc}",
                safe_reason="CSV file is not valid UTF-8 encoded text.",
            ) from exc

        if not text.strip():
            # Empty CSV
            empty_table = ParsedTable(headers=[], rows=[])
            return ParsedDocument(
                document_id=document_id,
                title=filename,
                source_type="csv",
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                pages=[],
                sections=[],
                tables=[empty_table],
                metadata={"row_count": 0, "col_count": 0, "delimiter": ","},
            )

        # Detect delimiter using sniffer on sample
        delimiter = ","
        sample = text[:4096]
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except Exception:
            # Fallback heuristic: count common delimiters in first line
            first_line = text.split("\n", 1)[0]
            for candidate in [",", ";", "\t", "|"]:
                if candidate in first_line:
                    delimiter = candidate
                    break

        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        try:
            all_rows = list(reader)
        except csv.Error as exc:
            raise ParsingError(
                f"Malformed CSV: {exc}",
                safe_reason="Malformed CSV formatting.",
            ) from exc

        if not all_rows:
            empty_table = ParsedTable(headers=[], rows=[])
            return ParsedDocument(
                document_id=document_id,
                title=filename,
                source_type="csv",
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                pages=[],
                sections=[],
                tables=[empty_table],
                metadata={"row_count": 0, "col_count": 0, "delimiter": delimiter},
            )

        # First row as headers
        headers = [c.strip() for c in all_rows[0]]
        data_rows = [[c.strip() for c in row] for row in all_rows[1:]]

        # Check limits
        total_rows = len(data_rows)
        if total_rows > limits.max_rows:
            raise ResourceLimitExceededError(
                f"CSV exceeds maximum row limit ({total_rows} > {limits.max_rows}).",
                safe_reason=f"Document exceeds maximum allowable row limit of {limits.max_rows}.",
            )

        char_count = sum(len(h) for h in headers) + sum(len(c) for r in data_rows for c in r)
        if char_count > limits.max_characters:
            raise ResourceLimitExceededError(
                f"CSV exceeds character limit ({char_count} > {limits.max_characters}).",
                safe_reason=(
                    f"Document exceeds maximum character extraction ceiling "
                    f"of {limits.max_characters}."
                ),
            )

        parsed_table = ParsedTable(
            headers=headers,
            rows=data_rows,
            metadata={"delimiter": delimiter, "row_count": total_rows, "col_count": len(headers)},
        )

        metadata: dict[str, Any] = {
            "delimiter": delimiter,
            "row_count": total_rows,
            "col_count": len(headers),
            "character_count": char_count,
            "table_count": 1,
        }

        return ParsedDocument(
            document_id=document_id,
            title=filename,
            source_type="csv",
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            pages=[],
            sections=[],
            tables=[parsed_table],
            metadata=metadata,
        )
