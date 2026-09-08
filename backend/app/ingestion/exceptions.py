"""Domain exceptions for document ingestion pipeline."""


class IngestionError(Exception):
    """Base exception for all ingestion failures."""

    def __init__(self, message: str, safe_reason: str | None = None) -> None:
        super().__init__(message)
        self.safe_reason = safe_reason or message


class ParsingError(IngestionError):
    """Raised when parsing fails due to malformed, corrupted, or unreadable document."""

    def __init__(
        self,
        message: str,
        safe_reason: str = "Document content is corrupted or unreadable.",
    ) -> None:
        super().__init__(message, safe_reason=safe_reason)


class ResourceLimitExceededError(IngestionError):
    """Raised when a document exceeds configured parsing limits (pages, rows, characters)."""

    def __init__(
        self,
        message: str,
        safe_reason: str = "Document exceeds allowable ingestion limits.",
    ) -> None:
        super().__init__(message, safe_reason=safe_reason)


class UnsupportedFormatError(IngestionError):
    """Raised when the document MIME type or format is not supported by any registered parser."""

    def __init__(
        self,
        message: str,
        safe_reason: str = "File format is not supported for parsing.",
    ) -> None:
        super().__init__(message, safe_reason=safe_reason)
