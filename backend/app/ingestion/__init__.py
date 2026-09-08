"""Document ingestion pipeline package."""

from app.ingestion.exceptions import (
    IngestionError,
    ParsingError,
    ResourceLimitExceededError,
    UnsupportedFormatError,
)
from app.ingestion.models import (
    BlockType,
    IngestionLimits,
    ParsedBlock,
    ParsedDocument,
    ParsedPage,
    ParsedSection,
    ParsedTable,
)
from app.ingestion.normalization import (
    normalize_block,
    normalize_document,
    normalize_page,
    normalize_section,
    normalize_table,
    normalize_text,
)
from app.ingestion.parsers import (
    CSVParser,
    DocumentParser,
    DOCXParser,
    PDFParser,
    TXTParser,
    XLSXParser,
)
from app.ingestion.resolver import ParserResolver
from app.ingestion.service import IngestionService

__all__ = [
    "BlockType",
    "CSVParser",
    "DOCXParser",
    "DocumentParser",
    "IngestionError",
    "IngestionLimits",
    "IngestionService",
    "PDFParser",
    "ParsedBlock",
    "ParsedDocument",
    "ParsedPage",
    "ParsedSection",
    "ParsedTable",
    "ParserResolver",
    "ParsingError",
    "ResourceLimitExceededError",
    "TXTParser",
    "UnsupportedFormatError",
    "XLSXParser",
    "normalize_block",
    "normalize_document",
    "normalize_page",
    "normalize_section",
    "normalize_table",
    "normalize_text",
]
