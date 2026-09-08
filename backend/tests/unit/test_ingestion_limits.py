"""Unit tests for ingestion resource limits and safe error boundaries."""

import io
import uuid

import openpyxl
import pytest
from pypdf import PdfWriter

from app.ingestion.exceptions import ResourceLimitExceededError
from app.ingestion.models import IngestionLimits
from app.ingestion.parsers.csv import CSVParser
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.txt import TXTParser
from app.ingestion.parsers.xlsx import XLSXParser


def test_pdf_page_limit_exceeded() -> None:
    parser = PDFParser()
    doc_id = uuid.uuid4()

    # Create a 5-page PDF
    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)

    # Limit to 3 pages
    strict_limits = IngestionLimits(max_pages=3)

    with pytest.raises(ResourceLimitExceededError) as exc_info:
        parser.parse(buf.getvalue(), doc_id, "big.pdf", strict_limits)

    assert "exceeds maximum allowable page limit" in exc_info.value.safe_reason
    # Ensure no internal path leakage
    assert "/" not in exc_info.value.safe_reason


def test_csv_row_limit_exceeded() -> None:
    parser = CSVParser()
    doc_id = uuid.uuid4()

    # Create CSV with 10 rows
    lines = ["Header1,Header2"] + [f"Val{i},Val{i}" for i in range(10)]
    csv_bytes = "\n".join(lines).encode("utf-8")

    strict_limits = IngestionLimits(max_rows=5)

    with pytest.raises(ResourceLimitExceededError) as exc_info:
        parser.parse(csv_bytes, doc_id, "big.csv", strict_limits)

    assert "exceeds maximum allowable row limit" in exc_info.value.safe_reason


def test_xlsx_sheet_limit_exceeded() -> None:
    parser = XLSXParser()
    doc_id = uuid.uuid4()

    wb = openpyxl.Workbook()
    for i in range(4):
        wb.create_sheet(title=f"Sheet_{i}")
    buf = io.BytesIO()
    wb.save(buf)

    strict_limits = IngestionLimits(max_sheets=2)

    with pytest.raises(ResourceLimitExceededError) as exc_info:
        parser.parse(buf.getvalue(), doc_id, "many_sheets.xlsx", strict_limits)

    assert "exceeds maximum allowable sheet limit" in exc_info.value.safe_reason


def test_character_limit_exceeded() -> None:
    parser = TXTParser()
    doc_id = uuid.uuid4()

    long_text = "A" * 10_000
    strict_limits = IngestionLimits(max_characters=1_000)

    with pytest.raises(ResourceLimitExceededError) as exc_info:
        parser.parse(long_text.encode("utf-8"), doc_id, "long.txt", strict_limits)

    assert "character extraction ceiling" in exc_info.value.safe_reason
