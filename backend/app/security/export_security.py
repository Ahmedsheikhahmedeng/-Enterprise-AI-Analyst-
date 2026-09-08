"""Export Security Module — TASK 22.

Provides protections against:
1. Spreadsheet / CSV Formula Injection (DDE attacks starting with =, +, -, @, \\t, \\r).
2. Export filename manipulation, path traversal, CRLF injection, and length abuse.
"""

from __future__ import annotations

import re
from typing import Any

from app.security.exceptions import ExportSecurityError
from app.security.sanitization import sanitize_header_value

# Characters that trigger formula execution in spreadsheet applications (Excel, Calc, Sheets)
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: Any) -> str:
    """Sanitize a single CSV/spreadsheet cell value against Formula Injection (CSV Injection).

    If the text starts with dangerous formula prefixes (=, +, -, @, \\t, \\r),
    prepend an apostrophe (') so spreadsheet software treats it as raw text literal.
    """
    if value is None:
        return ""

    text = str(value)
    if not text:
        return ""

    # Check direct formula prefix (including \t or \r) or after spaces
    if text.startswith(FORMULA_PREFIXES) or text.lstrip(" ").startswith(FORMULA_PREFIXES):
        # Prepend single quote to neutralize formula evaluation
        return f"'{text}"

    return text


def sanitize_export_filename(filename: str, max_length: int = 128) -> str:
    """Sanitize and validate an export filename to prevent:
    - Path traversal (../, ..\\, %2e%2e)
    - CRLF header injection
    - Null byte injection
    - Illegal filesystem characters
    - Unbounded length
    """
    if not filename:
        raise ExportSecurityError("Export filename cannot be empty")

    # 1. Check for CRLF or null bytes directly
    if "\r" in filename or "\n" in filename or "\x00" in filename:
        raise ExportSecurityError(
            f"Control characters or CRLF detected in export filename: '{filename}'"
        )

    cleaned = sanitize_header_value(filename).strip()

    # 2. Check for explicit path traversal attempts
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned or "%2e" in cleaned.lower():
        raise ExportSecurityError(f"Path traversal detected in export filename: '{filename}'")

    # 3. Allow only safe characters: alphanumerics, underscores, hyphens, and periods
    safe_name = re.sub(r"[^\w\.\-]", "_", cleaned)

    # 4. Enforce length bounds
    if len(safe_name) > max_length:
        # Keep extension if possible
        if "." in safe_name:
            stem, ext = safe_name.rsplit(".", 1)
            keep_len = max_length - len(ext) - 1
            safe_name = f"{stem[:keep_len]}.{ext}"
        else:
            safe_name = safe_name[:max_length]

    if not safe_name or safe_name == ".":
        raise ExportSecurityError("Export filename resolved to invalid or empty identifier")

    return safe_name
