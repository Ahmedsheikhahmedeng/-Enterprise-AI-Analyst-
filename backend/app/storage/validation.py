"""File validation, MIME type detection by magic bytes, and filename sanitization."""

import hashlib
import re
import tempfile
from pathlib import Path
from typing import BinaryIO, Final

from fastapi import UploadFile

from app.core.exceptions import PayloadTooLargeAppException, ValidationAppException

ALLOWED_EXTENSIONS: Final[set[str]] = {".pdf", ".docx", ".txt", ".csv", ".xlsx"}

MIME_TYPE_MAP: Final[dict[str, str]] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

# Magic byte signatures
PDF_MAGIC: Final[bytes] = b"%PDF-"
ZIP_MAGIC: Final[bytes] = b"PK\x03\x04"


def sanitize_filename(filename: str | None) -> str:
    """Sanitize original filename to prevent path traversal and header injection.

    Strips directory components and removes carriage returns, newlines, and control chars.
    """
    if not filename:
        return "unnamed_document"

    # Normalize Windows backslashes to forward slashes before extracting basename
    normalized = filename.replace("\\", "/")
    base = Path(normalized).name

    # Strip carriage returns, newlines, and control chars (CRLF injection prevention)
    cleaned = re.sub(r"[\r\n\x00-\x1f\x7f\\]", "", base).strip()
    # Normalize double quotes and semicolons for safe Content-Disposition
    cleaned = cleaned.replace('"', "").replace(";", "")

    if not cleaned or cleaned in (".", ".."):
        return "unnamed_document"

    return cleaned


def detect_mime_type_from_bytes(header: bytes, extension: str) -> str:
    """Detect MIME type from file header bytes and expected extension.

    Validates magic bytes against claimed extension:
    - .pdf must start with %PDF-
    - .docx and .xlsx must start with PK\x03\x04 (ZIP container)
    - .txt and .csv must be valid text without binary null bytes
    """
    ext = extension.lower()

    if ext == ".pdf":
        if header.startswith(PDF_MAGIC):
            return "application/pdf"
        raise ValidationAppException(
            message="File content does not match expected PDF signature.",
            code="MIME_SIGNATURE_MISMATCH",
            details={"expected_mime": "application/pdf"},
        )

    if ext in (".docx", ".xlsx"):
        if header.startswith(ZIP_MAGIC):
            return MIME_TYPE_MAP[ext]
        raise ValidationAppException(
            message=f"File content does not match expected Office OpenXML signature for {ext}.",
            code="MIME_SIGNATURE_MISMATCH",
            details={"expected_extension": ext},
        )

    if ext in (".txt", ".csv"):
        # Plain text / CSV should not contain binary null bytes
        if b"\x00" in header:
            raise ValidationAppException(
                message=f"File content contains binary null bytes, invalid for text file ({ext}).",
                code="MIME_SIGNATURE_MISMATCH",
                details={"expected_extension": ext},
            )
        try:
            # Check basic UTF-8/ASCII decodability
            header.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValidationAppException(
                message=f"Text file content is not valid UTF-8 encoded text for {ext}.",
                code="INVALID_TEXT_ENCODING",
            ) from exc
        return MIME_TYPE_MAP[ext]

    raise ValidationAppException(
        message=f"Unsupported file extension: {ext}",
        code="UNSUPPORTED_FILE_TYPE",
        details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS)},
    )


class ProcessedUpload:
    """Encapsulates validated upload payload with checksum and spool."""

    def __init__(
        self,
        spool: BinaryIO | tempfile.SpooledTemporaryFile[bytes],
        sha256: str,
        size: int,
        detected_mime: str,
        clean_filename: str,
        extension: str,
    ) -> None:
        self.spool = spool
        self.sha256 = sha256
        self.size = size
        self.detected_mime = detected_mime
        self.clean_filename = clean_filename
        self.extension = extension

    def close(self) -> None:
        """Close and discard the underlying temporary spool."""
        import contextlib

        with contextlib.suppress(Exception):
            self.spool.close()


async def validate_and_stream_upload(
    upload_file: UploadFile,
    max_bytes: int,
) -> ProcessedUpload:
    """Stream incoming UploadFile with bounded memory, calculate SHA-256, and validate MIME.

    Reads in 64KB chunks into a SpooledTemporaryFile (max 512KB in memory).
    Aborts immediately if the stream exceeds max_bytes.
    Rejects 0-byte (empty) files.
    """
    clean_filename = sanitize_filename(upload_file.filename)
    extension = Path(clean_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationAppException(
            message=f"File extension '{extension}' is not permitted.",
            code="UNSUPPORTED_FILE_TYPE",
            details={"allowed_extensions": sorted(ALLOWED_EXTENSIONS), "extension": extension},
        )

    hasher = hashlib.sha256()
    spool = tempfile.SpooledTemporaryFile(max_size=512 * 1024, mode="w+b")  # noqa: SIM115
    total_size = 0
    header_bytes = b""
    chunk_size = 64 * 1024

    try:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > max_bytes:
                spool.close()
                max_mb = max_bytes // (1024 * 1024)
                raise PayloadTooLargeAppException(
                    message=f"File size exceeds maximum permitted limit of {max_mb} MB.",
                    details={"max_bytes": max_bytes, "received_bytes": total_size},
                )

            if len(header_bytes) < 4096:
                needed = 4096 - len(header_bytes)
                header_bytes += chunk[:needed]

            hasher.update(chunk)
            spool.write(chunk)

        if total_size == 0:
            spool.close()
            raise ValidationAppException(
                message="Uploaded file is empty (0 bytes).",
                code="EMPTY_FILE",
            )

        detected_mime = detect_mime_type_from_bytes(header_bytes, extension)
        sha256_hex = hasher.hexdigest()

        # Rewind spool to beginning for storage provider consumption
        spool.seek(0)

        return ProcessedUpload(
            spool=spool,
            sha256=sha256_hex,
            size=total_size,
            detected_mime=detected_mime,
            clean_filename=clean_filename,
            extension=extension,
        )

    except Exception:
        spool.close()
        raise
