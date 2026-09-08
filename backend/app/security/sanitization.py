"""Sanitization utilities for XSS escaping, Unicode normalization, and CRLF protection."""

import html
import re
import unicodedata

# Regex matching CRLF control characters to prevent HTTP Response Splitting / Header Injection
CRLF_REGEX = re.compile(r"[\r\n]")


def escape_html(text: str | None) -> str:
    """Safely escape HTML meta-characters (&, <, >, ", ') to prevent Cross-Site Scripting (XSS)."""
    if not text:
        return ""
    return html.escape(str(text), quote=True)


def normalize_security_text(text: str | None) -> str:
    """Normalize text using Unicode NFKC normalization for robust security pattern matching.

    Preserves Arabic, Turkish, and multilingual content while resolving confusable full-width
    and compatibility characters.
    """
    if not text:
        return ""
    # NFKC decomposes and maps compatibility characters to standard equivalents
    normalized = unicodedata.normalize("NFKC", text)
    return normalized.strip()


def sanitize_header_value(value: str | None) -> str:
    """Strip carriage return (\r) and newline (\n) characters to prevent header injection attacks."""
    if not value:
        return ""
    # Strip any line-break sequence
    return CRLF_REGEX.sub("", str(value)).strip()
