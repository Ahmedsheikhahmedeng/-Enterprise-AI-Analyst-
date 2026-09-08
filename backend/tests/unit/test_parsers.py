"""Unit tests for document parsers, resolver, and normalization layer."""

import io
import uuid

import docx
import openpyxl
import pytest
from pypdf import PdfWriter

from app.ingestion.exceptions import ParsingError, UnsupportedFormatError
from app.ingestion.models import BlockType, IngestionLimits
from app.ingestion.normalization import normalize_document, normalize_text
from app.ingestion.parsers.csv import CSVParser
from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.txt import TXTParser
from app.ingestion.parsers.xlsx import XLSXParser
from app.ingestion.resolver import ParserResolver

DEFAULT_LIMITS = IngestionLimits(
    max_pages=500,
    max_rows=50000,
    max_sheets=20,
    max_characters=5_000_000,
)


def _make_pdf(pages_text: list[str], outline_title: str | None = None) -> bytes:
    """Helper creating real valid PDF bytes using pypdf."""
    writer = PdfWriter()
    for idx, _page_text in enumerate(pages_text):
        writer.add_blank_page(width=612, height=792)
        if idx == 0 and outline_title:
            writer.add_outline_item(outline_title, 0)

    # If text is provided, build a clean PDF with content stream
    if any(bool(t.strip()) for t in pages_text):
        # We can construct PDF 1.4 with text streams
        pdf_chunks = [
            "%PDF-1.4\n",
            "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        ]
        page_obj_ids = [3 + i * 2 for i in range(len(pages_text))]
        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        pdf_chunks.append(
            f"2 0 obj << /Type /Pages /Kids [{kids_str}] /Count {len(pages_text)} >> endobj\n"
        )

        for idx, text in enumerate(pages_text):
            page_id = 3 + idx * 2
            content_id = page_id + 1
            # Format lines with BT / ET
            lines = text.split("\n")
            stream_body = "BT\n/F1 12 Tf\n72 712 Td\n"
            for line in lines:
                escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                stream_body += f"({escaped}) Tj\n0 -15 Td\n"
            stream_body += "ET\n"

            stream_bytes = stream_body.encode("utf-8")
            pdf_chunks.append(
                f"{page_id} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_id} 0 R /Resources << /Font << /F1 "
                f"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >> endobj\n"
            )
            pdf_chunks.append(f"{content_id} 0 obj << /Length {len(stream_bytes)} >> stream\n")
            pdf_chunks.append(stream_body)
            pdf_chunks.append("endstream\nendobj\n")

        pdf_chunks.append(
            "xref\n0 1\n0000000000 65535 f \ntrailer << /Size 20 /Root 1 0 R >>\n"
            "startxref\n100\n%%EOF\n"
        )
        return "".join(pdf_chunks).encode("latin-1", errors="replace")

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ==============================================================================
# 1. PARSER RESOLVER TESTS
# ==============================================================================


def test_resolver_by_detected_mime() -> None:
    resolver = ParserResolver()
    parser = resolver.resolve(detected_mime_type="application/pdf")
    assert isinstance(parser, PDFParser)


def test_resolver_by_declared_mime() -> None:
    resolver = ParserResolver()
    parser = resolver.resolve(mime_type="text/csv")
    assert isinstance(parser, CSVParser)


def test_resolver_by_extension_fallback() -> None:
    resolver = ParserResolver()
    parser = resolver.resolve(
        mime_type="application/octet-stream",
        filename="report.xlsx",
    )
    assert isinstance(parser, XLSXParser)


def test_resolver_docx_mime() -> None:
    resolver = ParserResolver()
    parser = resolver.resolve(
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert isinstance(parser, DOCXParser)


def test_resolver_unsupported_format() -> None:
    resolver = ParserResolver()
    with pytest.raises(UnsupportedFormatError) as exc_info:
        resolver.resolve(mime_type="image/jpeg", filename="photo.jpg")
    assert "Unsupported file format" in exc_info.value.safe_reason


# ==============================================================================
# 2. PDF PARSER TESTS
# ==============================================================================


def test_pdf_parser_single_page() -> None:
    parser = PDFParser()
    doc_id = uuid.uuid4()
    pdf_bytes = _make_pdf(["Quarterly revenue reached 1.2M USD."])

    parsed = parser.parse(pdf_bytes, doc_id, "revenue.pdf", DEFAULT_LIMITS)

    assert parsed.document_id == doc_id
    assert parsed.source_type == "pdf"
    assert len(parsed.pages) == 1
    assert parsed.pages[0].page_number == 1
    assert any("Quarterly revenue" in b.text for b in parsed.pages[0].blocks)


def test_pdf_parser_multiple_pages() -> None:
    parser = PDFParser()
    doc_id = uuid.uuid4()
    pdf_bytes = _make_pdf(["Page 1 content here.", "Page 2 content here."])

    parsed = parser.parse(pdf_bytes, doc_id, "multipage.pdf", DEFAULT_LIMITS)

    assert len(parsed.pages) == 2
    assert parsed.pages[0].page_number == 1
    assert parsed.pages[1].page_number == 2


def test_pdf_parser_empty_page() -> None:
    parser = PDFParser()
    doc_id = uuid.uuid4()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)

    parsed = parser.parse(buf.getvalue(), doc_id, "empty.pdf", DEFAULT_LIMITS)
    assert len(parsed.pages) == 1
    assert len(parsed.pages[0].blocks) == 0


def test_pdf_parser_table_extraction() -> None:
    parser = PDFParser()
    doc_id = uuid.uuid4()
    # Table formatted with pipe delimiter
    table_text = "| Region | Revenue |\n| Europe | 1200000 |\n| Asia | 850000 |"
    pdf_bytes = _make_pdf([table_text])

    parsed = parser.parse(pdf_bytes, doc_id, "table.pdf", DEFAULT_LIMITS)

    assert len(parsed.tables) >= 1
    table = parsed.tables[0]
    assert "Region" in table.headers
    assert "Revenue" in table.headers
    assert len(table.rows) == 2
    assert table.rows[0] == ["Europe", "1200000"]
    assert table.rows[1] == ["Asia", "850000"]


def test_pdf_parser_corrupted_file() -> None:
    parser = PDFParser()
    doc_id = uuid.uuid4()
    with pytest.raises(ParsingError) as exc_info:
        parser.parse(b"NOT A VALID PDF FILE CONTENT", doc_id, "corrupt.pdf", DEFAULT_LIMITS)
    assert exc_info.value.safe_reason


# ==============================================================================
# 3. DOCX PARSER TESTS
# ==============================================================================


def test_docx_parser_order_and_elements() -> None:
    parser = DOCXParser()
    doc_id = uuid.uuid4()

    doc = docx.Document()
    doc.add_heading("Financial Report 2026", level=1)
    doc.add_paragraph("This is the executive summary paragraph.")
    # Add a table
    table = doc.add_table(rows=3, cols=2)
    table.cell(0, 0).text = "Metric"
    table.cell(0, 1).text = "Value"
    table.cell(1, 0).text = "EBITDA"
    table.cell(1, 1).text = "$4.5M"
    table.cell(2, 0).text = "Net Margin"
    table.cell(2, 1).text = "22%"
    # Add paragraph after table to verify ordering
    doc.add_paragraph("Subsequent notes after the metrics table.")
    # Add list
    doc.add_paragraph("Key Risk 1", style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)

    parsed = parser.parse(buf.getvalue(), doc_id, "report.docx", DEFAULT_LIMITS)

    assert parsed.source_type == "docx"
    assert len(parsed.tables) == 1
    assert parsed.tables[0].headers == ["Metric", "Value"]
    assert len(parsed.tables[0].rows) == 2
    assert parsed.tables[0].rows[0] == ["EBITDA", "$4.5M"]

    # Verify sections and blocks
    all_blocks = [b for s in parsed.sections for b in s.blocks]
    block_types = [b.type for b in all_blocks]
    assert BlockType.HEADING in block_types
    assert BlockType.PARAGRAPH in block_types
    assert BlockType.TABLE in block_types
    assert BlockType.LIST in block_types


def test_docx_parser_multilingual() -> None:
    parser = DOCXParser()
    doc_id = uuid.uuid4()

    doc = docx.Document()
    doc.add_paragraph("Türkçe: İstanbul, İzmir, Eskişehir. Şeker, ağaç, çiçek.")
    doc.add_paragraph("Arabic: تقرير مالي فصلي لأداء الشركة لعام 2026")

    buf = io.BytesIO()
    doc.save(buf)

    parsed = parser.parse(buf.getvalue(), doc_id, "multilingual.docx", DEFAULT_LIMITS)
    text_content = " ".join(b.text for s in parsed.sections for b in s.blocks)

    assert "İstanbul" in text_content
    assert "Şeker" in text_content
    assert "تقرير مالي" in text_content


def test_docx_parser_corrupted() -> None:
    parser = DOCXParser()
    doc_id = uuid.uuid4()
    with pytest.raises(ParsingError):
        parser.parse(b"PK\x03\x04corrupted zip payload", doc_id, "corrupt.docx", DEFAULT_LIMITS)


# ==============================================================================
# 4. TXT PARSER TESTS
# ==============================================================================


def test_txt_parser_utf8_multilingual() -> None:
    parser = TXTParser()
    doc_id = uuid.uuid4()
    text = (
        "# Strategic Overview\n\n"
        "English: Revenue grew 18% year-over-year.\n\n"
        "Türkçe: Şirketin yıllık geliri başarıyla arttı. Çarşamba günü toplantı yapıldı.\n\n"
        "Arabic: حققت الشركة نمواً ملحوظاً في الإيرادات السنوية."
    )

    parsed = parser.parse(text.encode("utf-8"), doc_id, "strategy.txt", DEFAULT_LIMITS)

    assert parsed.source_type == "txt"
    assert len(parsed.sections) == 1
    blocks = parsed.sections[0].blocks
    assert len(blocks) >= 3
    assert blocks[0].type == BlockType.HEADING
    assert "Strategic Overview" in blocks[0].text
    assert any("Şirketin" in b.text for b in blocks)
    assert any("حققت الشركة" in b.text for b in blocks)


def test_txt_parser_crlf_normalization() -> None:
    parser = TXTParser()
    doc_id = uuid.uuid4()
    text = "Paragraph One\r\n\r\nParagraph Two\r\n\r\nParagraph Three"

    parsed = parser.parse(text.encode("utf-8"), doc_id, "crlf.txt", DEFAULT_LIMITS)
    assert len(parsed.sections[0].blocks) == 3


def test_txt_parser_invalid_encoding() -> None:
    parser = TXTParser()
    doc_id = uuid.uuid4()
    # Invalid byte sequence for UTF-8
    with pytest.raises(ParsingError) as exc_info:
        parser.parse(b"\x80\x81\xff\xfe non-utf8", doc_id, "invalid.txt", DEFAULT_LIMITS)
    assert "valid UTF-8" in exc_info.value.safe_reason


def test_txt_parser_empty_file() -> None:
    parser = TXTParser()
    doc_id = uuid.uuid4()
    parsed = parser.parse(b"", doc_id, "empty.txt", DEFAULT_LIMITS)
    assert len(parsed.sections[0].blocks) == 0


# ==============================================================================
# 5. CSV PARSER TESTS
# ==============================================================================


def test_csv_parser_comma_delimiter() -> None:
    parser = CSVParser()
    doc_id = uuid.uuid4()
    csv_text = "Product,Price,Quantity\nLaptop,1200,5\nMonitor,300,10"

    parsed = parser.parse(csv_text.encode("utf-8"), doc_id, "sales.csv", DEFAULT_LIMITS)

    assert parsed.source_type == "csv"
    assert len(parsed.tables) == 1
    table = parsed.tables[0]
    assert table.headers == ["Product", "Price", "Quantity"]
    assert len(table.rows) == 2
    assert table.rows[0] == ["Laptop", "1200", "5"]
    assert table.rows[1] == ["Monitor", "300", "10"]


def test_csv_parser_semicolon_delimiter() -> None:
    parser = CSVParser()
    doc_id = uuid.uuid4()
    csv_text = "Country;City;Population\nTurkey;Istanbul;15500000\nGermany;Berlin;3700000"

    parsed = parser.parse(csv_text.encode("utf-8"), doc_id, "cities.csv", DEFAULT_LIMITS)

    assert len(parsed.tables) == 1
    table = parsed.tables[0]
    assert table.headers == ["Country", "City", "Population"]
    assert len(table.rows) == 2
    assert table.rows[0] == ["Turkey", "Istanbul", "15500000"]


def test_csv_parser_empty_values_preserved() -> None:
    parser = CSVParser()
    doc_id = uuid.uuid4()
    csv_text = "ID,Name,Department,Notes\n1,Alice,Sales,\n2,Bob,,Remote"

    parsed = parser.parse(csv_text.encode("utf-8"), doc_id, "employees.csv", DEFAULT_LIMITS)
    table = parsed.tables[0]
    assert table.rows[0] == ["1", "Alice", "Sales", ""]
    assert table.rows[1] == ["2", "Bob", "", "Remote"]


def test_csv_parser_duplicate_headers() -> None:
    parser = CSVParser()
    doc_id = uuid.uuid4()
    csv_text = "Metric,Metric,Value\nQ1,Q2,100"

    parsed = parser.parse(csv_text.encode("utf-8"), doc_id, "dup.csv", DEFAULT_LIMITS)
    assert parsed.tables[0].headers == ["Metric", "Metric", "Value"]
    assert parsed.tables[0].rows == [["Q1", "Q2", "100"]]


# ==============================================================================
# 6. XLSX PARSER TESTS
# ==============================================================================


def test_xlsx_parser_single_sheet() -> None:
    parser = XLSXParser()
    doc_id = uuid.uuid4()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Financials"
    ws.append(["Category", "Q1", "Q2"])
    ws.append(["Marketing", "50000", "60000"])
    ws.append(["R&D", "120000", "130000"])

    buf = io.BytesIO()
    wb.save(buf)

    parsed = parser.parse(buf.getvalue(), doc_id, "fin.xlsx", DEFAULT_LIMITS)

    assert parsed.source_type == "xlsx"
    assert len(parsed.tables) == 1
    table = parsed.tables[0]
    assert table.sheet_name == "Financials"
    assert table.headers == ["Category", "Q1", "Q2"]
    assert len(table.rows) == 2


def test_xlsx_parser_multiple_sheets_preserved() -> None:
    parser = XLSXParser()
    doc_id = uuid.uuid4()

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Revenue"
    ws1.append(["Year", "Amount"])
    ws1.append(["2025", "1000000"])

    ws2 = wb.create_sheet(title="Headcount")
    ws2.append(["Department", "Count"])
    ws2.append(["Engineering", "45"])
    ws2.append(["Sales", "30"])

    buf = io.BytesIO()
    wb.save(buf)

    parsed = parser.parse(buf.getvalue(), doc_id, "company.xlsx", DEFAULT_LIMITS)

    # Sheets must NOT be merged
    assert len(parsed.tables) == 2
    assert parsed.tables[0].sheet_name == "Revenue"
    assert parsed.tables[0].headers == ["Year", "Amount"]
    assert parsed.tables[1].sheet_name == "Headcount"
    assert parsed.tables[1].headers == ["Department", "Count"]
    assert len(parsed.tables[1].rows) == 2


def test_xlsx_parser_corrupted() -> None:
    parser = XLSXParser()
    doc_id = uuid.uuid4()
    with pytest.raises(ParsingError):
        parser.parse(b"Corrupted Excel Payload", doc_id, "corrupt.xlsx", DEFAULT_LIMITS)


# ==============================================================================
# 7. NORMALIZATION TESTS
# ==============================================================================


def test_normalize_text_multilingual_and_whitespace() -> None:
    raw = (
        "  Hello   World  \r\n\r\n\r\n  Türkçe:   şeker,  çiçek  "
        "\r\n\x00\x05  Arabic:   تقرير مالي   "
    )
    normalized = normalize_text(raw)

    assert "\r" not in normalized
    assert "\x00" not in normalized
    assert "Hello World" in normalized
    assert "Türkçe: şeker, çiçek" in normalized
    assert "Arabic: تقرير مالي" in normalized
    # Max two consecutive newlines preserved
    assert "\n\n\n" not in normalized


def test_normalize_document_full() -> None:
    parser = TXTParser()
    doc_id = uuid.uuid4()
    raw_txt = "  Title   \r\n\r\n  Paragraph 1   text  \r\n\r\n"
    parsed = parser.parse(raw_txt.encode("utf-8"), doc_id, "doc.txt", DEFAULT_LIMITS)

    normalized = normalize_document(parsed)

    assert normalized.metadata.get("normalized") is True
    assert normalized.total_character_count > 0
