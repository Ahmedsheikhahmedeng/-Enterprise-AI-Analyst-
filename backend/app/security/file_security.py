"""File upload security validation enforcing magic-byte signatures, extensions, and path traversal defense."""

import os
import re
from dataclasses import dataclass

from app.security.config import SecurityConfig, get_security_config
from app.security.exceptions import FileSecurityError

# Magic byte signatures for authorized enterprise document formats
MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "pdf": [b"%PDF-"],
    "docx": [b"PK\x03\x04"],  # ZIP container header
    "xlsx": [b"PK\x03\x04"],  # ZIP container header
}

FILENAME_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\x00]')


@dataclass(frozen=True)
class ValidatedFile:
    filename: str
    extension: str
    mime_type: str
    size_bytes: int


class FileSecurityValidator:
    """Validates uploaded files against extension spoofing, binary payloads, and path traversal."""

    def __init__(self, config: SecurityConfig | None = None) -> None:
        self.config = config or get_security_config()

    def validate_file(
        self,
        filename: str,
        content: bytes,
        claimed_mime: str | None = None,
    ) -> ValidatedFile:
        """Validate entire file content bytes and return a ValidatedFile record."""
        # Sanitize filename if traversal chars exist
        clean_name = self.sanitize_filename(filename)
        # Check size limit
        if len(content) > self.config.max_upload_size_bytes:
            raise FileSecurityError(
                message=f"File exceeds maximum allowed size ({self.config.max_upload_size_bytes} bytes).",
                reason="file_too_large",
            )
        # Check extension and magic bytes
        self.validate_upload(
            filename=clean_name,
            content_header=content[:1024],
            total_size=len(content),
            declared_mime=claimed_mime,
        )
        ext = clean_name.rsplit(".", 1)[-1].lower() if "." in clean_name else ""
        mime_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "txt": "text/plain",
            "csv": "text/csv",
        }
        resolved_mime = claimed_mime or mime_map.get(ext, "application/octet-stream")
        return ValidatedFile(
            filename=clean_name,
            extension=ext,
            mime_type=resolved_mime,
            size_bytes=len(content),
        )

    def sanitize_filename(self, raw_filename: str | None) -> str:
        """Sanitize filename removing path traversal indicators, directory separators, and control bytes."""
        if not raw_filename or not raw_filename.strip():
            return "unnamed_document.bin"

        # Extract only base filename component
        base = os.path.basename(raw_filename.strip())
        # Replace illegal characters
        clean = FILENAME_ILLEGAL_CHARS.sub("_", base)
        # Strip path traversal dots
        clean = re.sub(r"\.{2,}", ".", clean).strip(" ._")
        if not clean:
            clean = "sanitized_document.bin"
        return clean[:255]

    def validate_upload(
        self,
        filename: str,
        content_header: bytes,
        total_size: int = 0,
        declared_mime: str | None = None,
    ) -> str:
        """Thoroughly validate upload against size limits, extension rules, and binary magic bytes."""
        # 1. Size Limit Check
        if total_size > self.config.max_upload_size_bytes:
            raise FileSecurityError(
                message=f"File exceeds maximum allowed size ({self.config.max_upload_size_bytes} bytes).",
                reason="file_too_large",
            )

        # 2. Filename & Path Traversal Check
        if ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
            raise FileSecurityError(
                message="Filename contains dangerous path traversal or directory components.",
                reason="path_traversal_detected",
            )

        # 3. Extension Validation
        clean_filename = self.sanitize_filename(filename)
        ext = clean_filename.rsplit(".", 1)[-1].lower() if "." in clean_filename else ""

        if not ext:
            raise FileSecurityError(
                message="File missing required extension.",
                reason="missing_extension",
            )

        if ext in self.config.forbidden_upload_extensions:
            raise FileSecurityError(
                message=f"Forbidden file extension '.{ext}' is strictly prohibited.",
                reason="forbidden_extension",
            )

        if ext not in self.config.allowed_upload_extensions:
            raise FileSecurityError(
                message=f"Unsupported file extension '.{ext}'. Supported types: PDF, DOCX, XLSX, TXT, CSV.",
                reason="unsupported_extension",
            )

        # 4. Magic Byte Signature Verification
        if ext in MAGIC_SIGNATURES:
            expected_signatures = MAGIC_SIGNATURES[ext]
            has_valid_signature = any(content_header.startswith(sig) for sig in expected_signatures)
            if not has_valid_signature:
                raise FileSecurityError(
                    message=f"File content does not match genuine magic-byte signature for .{ext} format.",
                    reason="magic_byte_mismatch",
                )
        elif ext in ("txt", "csv"):
            # Plaintext / CSV: must not contain binary null bytes
            if b"\x00" in content_header[:1024]:
                raise FileSecurityError(
                    message="Binary null bytes detected in plaintext/CSV document.",
                    reason="binary_null_byte_detected",
                )

        return clean_filename


# Global singleton
_global_file_validator: FileSecurityValidator | None = None


def get_file_security_validator() -> FileSecurityValidator:
    """Singleton getter for FileSecurityValidator."""
    global _global_file_validator
    if _global_file_validator is None:
        _global_file_validator = FileSecurityValidator()
    return _global_file_validator
