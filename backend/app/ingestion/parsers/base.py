"""Abstract base class for document parsers."""

import uuid
from abc import ABC, abstractmethod

from app.ingestion.models import IngestionLimits, ParsedDocument


class DocumentParser(ABC):
    """Abstract parser interface producing canonical parsed documents."""

    parser_name: str
    parser_version: str
    supported_mime_types: set[str]

    @abstractmethod
    def parse(
        self,
        file_bytes: bytes,
        document_id: uuid.UUID,
        filename: str,
        limits: IngestionLimits,
    ) -> ParsedDocument:
        """Parse raw file bytes into a canonical ParsedDocument representation.

        Args:
            file_bytes: Raw binary content of the file.
            document_id: UUID of the document.
            filename: Original or sanitized filename.
            limits: Configurable resource limits.

        Returns:
            Canonical ParsedDocument.

        Raises:
            ParsingError: When file is corrupted or cannot be parsed.
            ResourceLimitExceededError: When document exceeds limits.
        """
        pass
