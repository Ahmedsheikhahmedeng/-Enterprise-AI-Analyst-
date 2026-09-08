"""Document ingestion service coordinating parsing, normalization, and persistence."""

import json
import logging
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.exceptions import IngestionError, ParsingError
from app.ingestion.models import IngestionLimits, ParsedDocument
from app.ingestion.normalization import normalize_document
from app.ingestion.resolver import ParserResolver
from app.models.document import Document
from app.storage import StorageProvider

logger = logging.getLogger("app.ingestion")


class IngestionService:
    """Orchestrates document ingestion, normalization, and structured persistence."""

    def __init__(
        self,
        db_session: AsyncSession,
        storage: StorageProvider,
        resolver: ParserResolver | None = None,
        limits: IngestionLimits | None = None,
    ) -> None:
        self.db = db_session
        self.storage = storage
        self.resolver = resolver or ParserResolver()
        if limits is None:
            cfg = get_settings()
            limits = IngestionLimits(
                max_pages=cfg.MAX_INGESTION_PAGES,
                max_rows=cfg.MAX_INGESTION_ROWS,
                max_sheets=cfg.MAX_INGESTION_SHEETS,
                max_characters=cfg.MAX_EXTRACTED_CHARACTERS,
            )
        self.limits = limits

    async def ingest_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> ParsedDocument:
        """Ingest a document by tenant organization_id and document_id.

        Transitions:
        uploaded/failed -> processing -> parsed (or failed)
        """
        start_time = time.perf_counter()

        # 1. Fetch document strictly scoped by tenant organization_id
        stmt = select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
            Document.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()

        if not document:
            raise IngestionError(
                f"Document {document_id} not found in organization {organization_id}.",
                safe_reason="Document not found.",
            )

        # Log ingestion started
        logger.info(
            "ingestion_started",
            extra={
                "document_id": str(document_id),
                "organization_id": str(organization_id),
                "filename": document.original_filename,
                "mime_type": document.mime_type,
            },
        )

        # Mark document as processing
        document.status = "processing"
        document.failure_reason = None
        await self.db.commit()
        await self.db.refresh(document)

        try:
            # 2. Retrieve file content from storage provider
            file_bytes = await self.storage.read_bytes(document.storage_key)
            if not file_bytes:
                raise IngestionError(
                    f"File bytes not found at storage key {document.storage_key}.",
                    safe_reason="Stored document file could not be retrieved.",
                )

            # 3. Resolve appropriate parser
            parser = self.resolver.resolve(
                mime_type=document.mime_type,
                detected_mime_type=document.detected_mime_type,
                filename=document.original_filename,
            )

            logger.info(
                "ingestion_parser_selected",
                extra={
                    "document_id": str(document_id),
                    "organization_id": str(organization_id),
                    "parser": parser.parser_name,
                    "parser_version": parser.parser_version,
                },
            )

            # 4. Parse document
            raw_parsed_doc = parser.parse(
                file_bytes=file_bytes,
                document_id=document.id,
                filename=document.original_filename,
                limits=self.limits,
            )

            # 5. Normalize document
            parsed_doc = normalize_document(raw_parsed_doc)

            # 6. Persist canonical parsed JSON artifact to storage
            parsed_storage_key = (
                f"organizations/{organization_id}/documents/{document_id}/parsed.json"
            )
            parsed_json_bytes = parsed_doc.model_dump_json(indent=2).encode("utf-8")
            await self.storage.save(
                object_key=parsed_storage_key,
                data=parsed_json_bytes,
                content_type="application/json",
            )

            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # 7. Update PostgreSQL metadata and status
            document.status = "parsed"
            document.failure_reason = None
            document.parsed_storage_key = parsed_storage_key
            document.parser_name = parsed_doc.parser_name
            document.parser_version = parsed_doc.parser_version
            document.parsed_at = datetime.now(UTC)

            # Extract page count
            if parsed_doc.pages:
                document.page_count = len(parsed_doc.pages)
            elif parsed_doc.tables and parsed_doc.source_type == "xlsx":
                document.page_count = len(parsed_doc.tables)
            else:
                document.page_count = 1

            # Update document metadata
            doc_metadata = dict(document.metadata_ or {})
            doc_metadata.update(parsed_doc.metadata)
            doc_metadata["parse_duration_ms"] = duration_ms
            document.metadata_ = doc_metadata

            await self.db.commit()
            await self.db.refresh(document)

            logger.info(
                "ingestion_completed",
                extra={
                    "document_id": str(document_id),
                    "organization_id": str(organization_id),
                    "parser": parser.parser_name,
                    "duration_ms": duration_ms,
                    "page_count": document.page_count,
                    "character_count": parsed_doc.total_character_count,
                },
            )

            return parsed_doc

        except IngestionError as exc:
            await self.db.rollback()
            await self._mark_failed(organization_id, document_id, exc.safe_reason)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(
                "ingestion_failed",
                extra={
                    "document_id": str(document_id),
                    "organization_id": str(organization_id),
                    "error": str(exc),
                    "safe_reason": exc.safe_reason,
                    "duration_ms": duration_ms,
                },
            )
            raise

        except Exception as exc:
            await self.db.rollback()
            safe_reason = "An unexpected error occurred during document parsing."
            await self._mark_failed(organization_id, document_id, safe_reason)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.exception(
                "ingestion_failed_unexpected",
                extra={
                    "document_id": str(document_id),
                    "organization_id": str(organization_id),
                    "duration_ms": duration_ms,
                },
            )
            raise ParsingError(str(exc), safe_reason=safe_reason) from exc

    async def _mark_failed(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
        safe_reason: str,
    ) -> None:
        """Safely record failure status on document in PostgreSQL."""
        try:
            stmt = select(Document).where(
                Document.id == document_id,
                Document.organization_id == organization_id,
            )
            result = await self.db.execute(stmt)
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.failure_reason = safe_reason
                await self.db.commit()
        except Exception:
            await self.db.rollback()
            logger.error(
                "Failed to update document failure status in database",
                extra={"document_id": str(document_id)},
            )

    async def get_parsed_document(
        self,
        organization_id: uuid.UUID,
        document_id: uuid.UUID,
    ) -> ParsedDocument | None:
        """Retrieve stored canonical ParsedDocument artifact for a document."""
        stmt = select(Document).where(
            Document.id == document_id,
            Document.organization_id == organization_id,
            Document.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        if not document or not document.parsed_storage_key:
            return None

        try:
            data = await self.storage.read_bytes(document.parsed_storage_key)
        except Exception:
            return None
        if not data:
            return None

        parsed_json = json.loads(data.decode("utf-8"))
        return ParsedDocument.model_validate(parsed_json)
