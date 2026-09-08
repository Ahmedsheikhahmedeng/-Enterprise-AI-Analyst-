"""Unit tests for file validation, MIME type detection, filename sanitization, and streaming."""

import io

import pytest
from fastapi import UploadFile

from app.core.exceptions import PayloadTooLargeAppException, ValidationAppException
from app.storage.validation import (
    PDF_MAGIC,
    ZIP_MAGIC,
    detect_mime_type_from_bytes,
    sanitize_filename,
    validate_and_stream_upload,
)


# ===========================================================================
# 1. FILENAME SANITIZATION & CRLF DEFENSE TESTS
# ===========================================================================
@pytest.mark.parametrize(
    ("raw_filename", "expected_sanitized"),
    [
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd.txt", "passwd.txt"),
        ("..\\windows\\system32\\calc.exe", "calc.exe"),
        ("/root/secret/data.csv", "data.csv"),
        ("injected\r\nSet-Cookie: session=evil.pdf", "injectedSet-Cookie: session=evil.pdf"),
        ('bad"quotes;semi.docx', "badquotessemi.docx"),
        ("", "unnamed_document"),
        (None, "unnamed_document"),
        ("..", "unnamed_document"),
        (".", "unnamed_document"),
    ],
)
def test_filename_sanitization(raw_filename: str | None, expected_sanitized: str) -> None:
    """Verify filenames are properly sanitized to block path traversal and header injection."""
    sanitized = sanitize_filename(raw_filename)
    assert sanitized == expected_sanitized
    assert "/" not in sanitized
    assert "\\" not in sanitized
    assert "\r" not in sanitized
    assert "\n" not in sanitized
    assert '"' not in sanitized
    assert ";" not in sanitized


# ===========================================================================
# 2. MIME & MAGIC BYTE DETECTION TESTS
# ===========================================================================
def test_detect_valid_pdf_signature() -> None:
    """Verify PDF magic bytes %PDF- are recognized."""
    header = PDF_MAGIC + b"1.7\n%some binary data"
    mime = detect_mime_type_from_bytes(header, ".pdf")
    assert mime == "application/pdf"


def test_detect_invalid_pdf_mismatch() -> None:
    """Verify PDF with non-PDF bytes is rejected."""
    fake_header = b"This is plain text pretending to be a PDF"
    with pytest.raises(ValidationAppException) as exc_info:
        detect_mime_type_from_bytes(fake_header, ".pdf")
    assert exc_info.value.code == "MIME_SIGNATURE_MISMATCH"


def test_detect_valid_docx_and_xlsx_signature() -> None:
    """Verify Office OpenXML ZIP signatures PK\\x03\\x04 are recognized."""
    header = ZIP_MAGIC + b"rest of zip content"
    assert (
        detect_mime_type_from_bytes(header, ".docx")
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert (
        detect_mime_type_from_bytes(header, ".xlsx")
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_detect_invalid_docx_signature() -> None:
    """Verify DOCX with non-ZIP bytes is rejected."""
    header = b"Not a real docx"
    with pytest.raises(ValidationAppException) as exc_info:
        detect_mime_type_from_bytes(header, ".docx")
    assert exc_info.value.code == "MIME_SIGNATURE_MISMATCH"


def test_detect_valid_txt_and_csv() -> None:
    """Verify plain text and CSV decodable content is recognized."""
    text_header = b"col1,col2,col3\nval1,val2,val3\n"
    assert detect_mime_type_from_bytes(text_header, ".txt") == "text/plain"
    assert detect_mime_type_from_bytes(text_header, ".csv") == "text/csv"


def test_detect_text_with_null_bytes_rejected() -> None:
    """Verify text or CSV with binary null bytes is rejected as mismatched binary."""
    binary_in_text = b"text content with null byte \x00 in middle"
    with pytest.raises(ValidationAppException) as exc_info:
        detect_mime_type_from_bytes(binary_in_text, ".txt")
    assert exc_info.value.code == "MIME_SIGNATURE_MISMATCH"


def test_detect_unsupported_extension() -> None:
    """Verify unsupported extensions are rejected."""
    with pytest.raises(ValidationAppException) as exc_info:
        detect_mime_type_from_bytes(b"content", ".exe")
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


# ===========================================================================
# 3. STREAMING UPLOAD VALIDATION TESTS
# ===========================================================================
@pytest.mark.asyncio
async def test_validate_stream_valid_pdf() -> None:
    """Verify streaming upload of valid PDF calculates SHA-256 and detects MIME."""
    content = PDF_MAGIC + b"1.4 Sample PDF content for testing."
    file_io = io.BytesIO(content)
    upload_file = UploadFile(file=file_io, filename="valid_doc.pdf")

    processed = await validate_and_stream_upload(upload_file, max_bytes=10 * 1024 * 1024)
    try:
        assert processed.size == len(content)
        assert processed.extension == ".pdf"
        assert processed.detected_mime == "application/pdf"
        assert len(processed.sha256) == 64  # Hex SHA-256 is 64 chars

        # Verify spooled content matches original
        spooled_bytes = processed.spool.read()
        assert spooled_bytes == content
    finally:
        processed.close()


@pytest.mark.asyncio
async def test_validate_stream_empty_file_rejected() -> None:
    """Verify 0-byte file is rejected with EMPTY_FILE."""
    empty_file = UploadFile(file=io.BytesIO(b""), filename="empty.txt")
    with pytest.raises(ValidationAppException) as exc_info:
        await validate_and_stream_upload(empty_file, max_bytes=1024 * 1024)
    assert exc_info.value.code == "EMPTY_FILE"


@pytest.mark.asyncio
async def test_validate_stream_oversized_file_rejected() -> None:
    """Verify streaming upload exceeding max_bytes raises PayloadTooLargeAppException."""
    max_bytes = 1000  # 1000 bytes limit
    large_payload = b"A" * 2000
    oversized_file = UploadFile(file=io.BytesIO(large_payload), filename="large.txt")

    with pytest.raises(PayloadTooLargeAppException):
        await validate_and_stream_upload(oversized_file, max_bytes=max_bytes)


@pytest.mark.asyncio
async def test_validate_stream_unsupported_extension_rejected() -> None:
    """Verify unsupported file extensions are immediately rejected."""
    bad_file = UploadFile(file=io.BytesIO(b"some binary payload"), filename="malware.sh")
    with pytest.raises(ValidationAppException) as exc_info:
        await validate_and_stream_upload(bad_file, max_bytes=1024 * 1024)
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"
