"""Excel (XLSX) workbook parser preserving sheet boundaries and tabular grid."""

import io
import uuid
from typing import Any

import openpyxl

from app.ingestion.exceptions import ParsingError, ResourceLimitExceededError
from app.ingestion.models import (
    BlockType,
    IngestionLimits,
    ParsedBlock,
    ParsedDocument,
    ParsedTable,
)
from app.ingestion.parsers.base import DocumentParser


class XLSXParser(DocumentParser):
    """Parser for Excel workbooks preserving multi-sheet structure."""

    parser_name: str = "openpyxl"
    parser_version: str = "3.1.5"
    supported_mime_types: set[str] = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }

    def parse(
        self,
        file_bytes: bytes,
        document_id: uuid.UUID,
        filename: str,
        limits: IngestionLimits,
    ) -> ParsedDocument:
        try:
            wb = openpyxl.load_workbook(
                filename=io.BytesIO(file_bytes),
                read_only=True,
                data_only=True,  # evaluate formulas to cached values
            )
        except Exception as exc:
            raise ParsingError(f"Corrupted or invalid XLSX workbook: {exc}") from exc

        try:
            sheet_names = wb.sheetnames
            if len(sheet_names) > limits.max_sheets:
                raise ResourceLimitExceededError(
                    f"Workbook exceeds maximum sheet limit "
                    f"({len(sheet_names)} > {limits.max_sheets}).",
                    safe_reason=(
                        f"Workbook exceeds maximum allowable sheet limit of {limits.max_sheets}."
                    ),
                )

            tables: list[ParsedTable] = []
            blocks: list[ParsedBlock] = []
            cumulative_characters = 0
            cumulative_rows = 0

            for sheet_name in sheet_names:
                ws = wb[sheet_name]
                sheet_rows: list[list[str]] = []

                # Iterate rows safely
                for row in ws.iter_rows(values_only=True):
                    # Convert row values to string, handling None as ""
                    row_strs = [str(val).strip() if val is not None else "" for val in row]
                    # Check if row is entirely empty
                    if any(cell != "" for cell in row_strs):
                        sheet_rows.append(row_strs)

                if not sheet_rows:
                    # Empty sheet
                    tables.append(
                        ParsedTable(
                            headers=[],
                            rows=[],
                            sheet_name=sheet_name,
                            metadata={"sheet_name": sheet_name, "row_count": 0, "col_count": 0},
                        )
                    )
                    continue

                cumulative_rows += len(sheet_rows)
                if cumulative_rows > limits.max_rows:
                    raise ResourceLimitExceededError(
                        f"Workbook exceeds maximum row limit "
                        f"({cumulative_rows} > {limits.max_rows}).",
                        safe_reason=(
                            f"Workbook exceeds maximum allowable row limit of {limits.max_rows}."
                        ),
                    )

                # Normalize column lengths across rows in this sheet
                max_cols = max(len(r) for r in sheet_rows)
                normalized_rows = [r + [""] * (max_cols - len(r)) for r in sheet_rows]

                headers = normalized_rows[0]
                data_rows = normalized_rows[1:]

                sheet_chars = sum(len(h) for h in headers) + sum(
                    len(c) for r in data_rows for c in r
                )
                cumulative_characters += sheet_chars
                if cumulative_characters > limits.max_characters:
                    raise ResourceLimitExceededError(
                        f"Workbook exceeds character limit "
                        f"({cumulative_characters} > {limits.max_characters}).",
                        safe_reason=(
                            f"Document exceeds maximum character extraction ceiling "
                            f"of {limits.max_characters}."
                        ),
                    )

                table = ParsedTable(
                    headers=headers,
                    rows=data_rows,
                    sheet_name=sheet_name,
                    metadata={
                        "sheet_name": sheet_name,
                        "row_count": len(data_rows),
                        "col_count": max_cols,
                    },
                )
                tables.append(table)

                blocks.append(
                    ParsedBlock(
                        type=BlockType.TABLE,
                        text=f"Sheet '{sheet_name}' ({max_cols} cols, {len(data_rows)} rows)",
                        metadata={"sheet_name": sheet_name},
                    )
                )

            metadata: dict[str, Any] = {
                "sheet_count": len(sheet_names),
                "table_count": len(tables),
                "total_rows": cumulative_rows,
                "character_count": cumulative_characters,
            }

            return ParsedDocument(
                document_id=document_id,
                title=filename,
                source_type="xlsx",
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                pages=[],
                sections=[],
                tables=tables,
                metadata=metadata,
            )
        finally:
            wb.close()
