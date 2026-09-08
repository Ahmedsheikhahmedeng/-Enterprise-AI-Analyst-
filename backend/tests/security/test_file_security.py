"""File Upload Security Tests — TASK 22.

Verifies:
- Magic-byte validation preventing MIME spoofing (e.g. executable disguised as PDF)
- Dangerous file extension rejection (.exe, .sh, .html, .svg)
- Path traversal protection in filenames
- File size boundary checks
"""

import pytest

from app.security.config import SecurityConfig
from app.security.exceptions import FileSecurityError
from app.security.file_security import FileSecurityValidator


@pytest.fixture
def validator() -> FileSecurityValidator:
    cfg = SecurityConfig(max_upload_size_bytes=1024 * 1024)
    return FileSecurityValidator(cfg)


def test_valid_pdf_file_passes(validator: FileSecurityValidator) -> None:
    valid_pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    validated = validator.validate_file(
        filename="quarterly_report.pdf",
        content=valid_pdf_content,
        claimed_mime="application/pdf",
    )
    assert validated.extension == "pdf"
    assert validated.mime_type == "application/pdf"
    assert validated.size_bytes == len(valid_pdf_content)


def test_mime_spoofed_pdf_rejected(validator: FileSecurityValidator) -> None:
    # An executable payload claiming to be a PDF
    fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    with pytest.raises(FileSecurityError) as exc:
        validator.validate_file(
            filename="malicious.pdf",
            content=fake_pdf,
            claimed_mime="application/pdf",
        )
    assert "magic-byte signature" in str(exc.value).lower()


@pytest.mark.parametrize(
    "dangerous_filename",
    [
        "script.exe",
        "payload.sh",
        "attack.dll",
        "page.html",
        "vector.svg",
        "run.bat",
        "code.js",
    ],
)
def test_dangerous_extensions_rejected(
    validator: FileSecurityValidator,
    dangerous_filename: str,
) -> None:
    content = b"echo 'hello'"
    with pytest.raises(FileSecurityError) as exc:
        validator.validate_file(
            filename=dangerous_filename,
            content=content,
        )
    assert (
        ("prohibited" in str(exc.value).lower())
        or ("unsupported" in str(exc.value).lower())
        or ("extension" in str(exc.value).lower())
    )


@pytest.mark.parametrize(
    "traversal_filename,expected_clean_substring",
    [
        ("../../etc/passwd.txt", "passwd.txt"),
        ("..\\..\\boot.ini.txt", "boot.ini.txt"),
        ("normal_file.txt", "normal_file.txt"),
    ],
)
def test_path_traversal_filename_sanitized(
    validator: FileSecurityValidator,
    traversal_filename: str,
    expected_clean_substring: str,
) -> None:
    content = b"Safe plain text analytical notes."
    validated = validator.validate_file(
        filename=traversal_filename,
        content=content,
    )
    assert ".." not in validated.filename
    assert "/" not in validated.filename
    assert "\\" not in validated.filename
    assert expected_clean_substring in validated.filename


def test_oversized_file_upload_rejected(validator: FileSecurityValidator) -> None:
    # Exceeds max_upload_size_bytes (1 MB)
    large_content = b"X" * (1024 * 1024 + 10)
    with pytest.raises(FileSecurityError) as exc:
        validator.validate_file(
            filename="huge.txt",
            content=large_content,
        )
    assert "exceeds maximum allowed size" in str(exc.value)
