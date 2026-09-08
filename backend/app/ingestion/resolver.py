"""Parser resolver selecting appropriate parser based on MIME type and file attributes."""

import mimetypes
from pathlib import Path

from app.ingestion.exceptions import UnsupportedFormatError
from app.ingestion.parsers.base import DocumentParser
from app.ingestion.parsers.csv import CSVParser
from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.txt import TXTParser
from app.ingestion.parsers.xlsx import XLSXParser


class ParserResolver:
    """Registry and resolver mapping MIME types to appropriate DocumentParser."""

    def __init__(self) -> None:
        self._parsers_by_mime: dict[str, DocumentParser] = {}
        self._parsers_by_ext: dict[str, DocumentParser] = {}
        self._register_default_parsers()

    def register_parser(
        self,
        parser: DocumentParser,
        additional_extensions: list[str] | None = None,
    ) -> None:
        """Register a parser instance for its supported MIME types and extensions."""
        for mime in parser.supported_mime_types:
            self._parsers_by_mime[mime.lower().strip()] = parser

        if additional_extensions:
            for ext in additional_extensions:
                cleaned_ext = ext.lower().strip()
                if not cleaned_ext.startswith("."):
                    cleaned_ext = f".{cleaned_ext}"
                self._parsers_by_ext[cleaned_ext] = parser

    def _register_default_parsers(self) -> None:
        """Initialize standard parsers with their canonical MIME types and extensions."""
        pdf_parser = PDFParser()
        docx_parser = DOCXParser()
        txt_parser = TXTParser()
        csv_parser = CSVParser()
        xlsx_parser = XLSXParser()

        self.register_parser(pdf_parser, [".pdf"])
        self.register_parser(docx_parser, [".docx", ".doc"])
        self.register_parser(txt_parser, [".txt", ".text", ".md"])
        self.register_parser(csv_parser, [".csv"])
        self.register_parser(xlsx_parser, [".xlsx", ".xls"])

    def resolve(
        self,
        mime_type: str | None = None,
        detected_mime_type: str | None = None,
        filename: str | None = None,
    ) -> DocumentParser:
        """Resolve a DocumentParser based on trusted file metadata.

        Evaluation order:
        1. detected_mime_type (from file signature)
        2. declared mime_type
        3. filename extension fallback if mime_type is generic
        """
        # 1. Check detected MIME type
        if detected_mime_type:
            cleaned = detected_mime_type.lower().strip().split(";")[0]
            if cleaned in self._parsers_by_mime:
                return self._parsers_by_mime[cleaned]

        # 2. Check declared MIME type
        if mime_type:
            cleaned = mime_type.lower().strip().split(";")[0]
            if cleaned in self._parsers_by_mime:
                return self._parsers_by_mime[cleaned]

        # 3. Fallback: inspect extension
        if filename:
            ext = Path(filename).suffix.lower()
            if ext in self._parsers_by_ext:
                return self._parsers_by_ext[ext]

            # Try mimetypes guess
            guessed_type, _ = mimetypes.guess_type(filename)
            if guessed_type and guessed_type.lower() in self._parsers_by_mime:
                return self._parsers_by_mime[guessed_type.lower()]

        effective_mime = detected_mime_type or mime_type or "unknown"
        raise UnsupportedFormatError(
            f"No parser available for MIME type '{effective_mime}' (filename: '{filename}').",
            safe_reason=f"Unsupported file format: {effective_mime}.",
        )
