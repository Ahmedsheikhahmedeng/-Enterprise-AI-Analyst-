"""Document management service handling upload, download, deletion, and lifecycle."""

import contextlib
import uuid
from collections.abc import AsyncIterator, Sequence

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import ConflictAppException, NotFoundAppException
from app.core.logging import get_logger
from app.models.document import Document
from app.repositories.document import DocumentRepository
from app.storage.base import StorageProvider
from app.storage.validation import validate_and_stream_upload
from app.tenancy.context import TenantContext

logger = get_logger("services.document")


class DocumentService:
    """Enterprise document service providing storage orchestration, deduplication, and lifecycle."""

    def __init__(
        self,
        storage_provider: StorageProvider,
        document_repo: DocumentRepository | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.storage_provider = storage_provider
        self.document_repo = document_repo or DocumentRepository()
        self.settings = settings or get_settings()

    async def upload_document(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        file: UploadFile,
    ) -> Document:
        """Upload document with validation, checksum, deduplication, and atomic cleanup."""
        logger.info(
            "Starting document upload",
            audit_event="document_upload_started",
            organization_id=str(tenant.organization_id),
            user_id=str(tenant.user_id),
            raw_filename=file.filename,
        )

        max_bytes = self.settings.max_upload_size_bytes
        processed = await validate_and_stream_upload(file, max_bytes=max_bytes)

        try:
            # 1. Tenant-scoped duplicate detection via SHA-256
            existing = await self.document_repo.get_by_checksum(
                session=session,
                organization_id=tenant.organization_id,
                sha256=processed.sha256,
            )
            if existing is not None:
                logger.warning(
                    "Duplicate document detected for organization",
                    audit_event="duplicate_document_detected",
                    organization_id=str(tenant.organization_id),
                    user_id=str(tenant.user_id),
                    sha256=processed.sha256,
                    existing_document_id=str(existing.id),
                )
                raise ConflictAppException(
                    message=(
                        "A document with identical content already exists in this organization."
                    ),
                    code="DUPLICATE_DOCUMENT",
                    details={
                        "existing_document_id": str(existing.id),
                        "sha256": processed.sha256,
                        "filename": processed.clean_filename,
                    },
                )

            # 2. Server-controlled, random object key within tenant namespace
            object_key = self.storage_provider.generate_object_key(
                organization_id=tenant.organization_id,
                file_extension=processed.extension,
            )

            # 3. Persist file to storage provider
            await self.storage_provider.save(
                object_key=object_key,
                data=processed.spool,
                content_type=processed.detected_mime,
            )

            # 4. Insert Document metadata row in database
            try:
                document = await self.document_repo.create(
                    session=session,
                    organization_id=tenant.organization_id,
                    name=processed.clean_filename,
                    original_filename=processed.clean_filename,
                    mime_type=processed.detected_mime,
                    detected_mime_type=processed.detected_mime,
                    file_size=processed.size,
                    sha256=processed.sha256,
                    storage_backend=self.settings.STORAGE_BACKEND,
                    storage_key=object_key,
                    status="uploaded",
                    created_by=tenant.user_id,
                )
                await session.commit()
            except IntegrityError as exc:
                logger.warning(
                    "Concurrent duplicate document upload detected via database constraint",
                    audit_event="duplicate_document_detected",
                    organization_id=str(tenant.organization_id),
                    user_id=str(tenant.user_id),
                    sha256=processed.sha256,
                )
                await self.storage_provider.delete(object_key)
                await session.rollback()
                raise ConflictAppException(
                    message=(
                        "A document with identical content already exists in this organization."
                    ),
                    code="DUPLICATE_DOCUMENT",
                    details={
                        "sha256": processed.sha256,
                        "filename": processed.clean_filename,
                    },
                ) from exc
            except Exception as exc:
                # 5. Atomic cleanup: purge orphaned file from storage if DB transaction fails
                logger.error(
                    "Database transaction failed during upload; deleting orphaned storage object",
                    audit_event="storage_orphan_cleanup",
                    organization_id=str(tenant.organization_id),
                    object_key=object_key,
                    error=str(exc),
                )
                await self.storage_provider.delete(object_key)
                await session.rollback()
                raise

            logger.info(
                "Document upload completed successfully",
                audit_event="document_upload_completed",
                document_id=str(document.id),
                organization_id=str(tenant.organization_id),
                user_id=str(tenant.user_id),
                sha256=processed.sha256,
                file_size=processed.size,
            )
            return document

        finally:
            processed.close()

    async def get_document(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        document_id: uuid.UUID,
    ) -> Document:
        """Retrieve single document scoped strictly to tenant."""
        doc = await self.document_repo.get_by_id(
            session=session,
            id=document_id,
            organization_id=tenant.organization_id,
        )
        if doc is None:
            raise NotFoundAppException(
                message="Document not found.",
                code="NOT_FOUND",
            )
        return doc

    async def list_documents(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Document], int]:
        """List tenant documents and return total count."""
        items = await self.document_repo.list(
            session=session,
            organization_id=tenant.organization_id,
            skip=skip,
            limit=limit,
        )
        total = await self.document_repo.count(
            session=session,
            organization_id=tenant.organization_id,
        )
        return items, total

    async def download_document(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        document_id: uuid.UUID,
    ) -> tuple[Document, AsyncIterator[bytes]]:
        """Retrieve document metadata and stream from storage provider."""
        doc = await self.get_document(session=session, tenant=tenant, document_id=document_id)

        stream = await self.storage_provider.read(doc.storage_key)

        logger.info(
            "Document downloaded",
            audit_event="document_downloaded",
            document_id=str(doc.id),
            organization_id=str(tenant.organization_id),
            user_id=str(tenant.user_id),
            original_filename=doc.original_filename,
        )
        return doc, stream

    async def delete_document(
        self,
        session: AsyncSession,
        tenant: TenantContext,
        document_id: uuid.UUID,
    ) -> bool:
        """Safely soft-delete document in database and purge physical file from storage."""
        doc = await self.get_document(session=session, tenant=tenant, document_id=document_id)

        # Delete physical objects from storage provider
        await self.storage_provider.delete(doc.storage_key)
        if doc.parsed_storage_key:
            with contextlib.suppress(Exception):
                await self.storage_provider.delete(doc.parsed_storage_key)

        # Soft-delete record in database
        success = await self.document_repo.soft_delete(
            session=session,
            id=document_id,
            organization_id=tenant.organization_id,
        )
        await session.commit()

        logger.info(
            "Document deleted",
            audit_event="document_deleted",
            document_id=str(doc.id),
            organization_id=str(tenant.organization_id),
            user_id=str(tenant.user_id),
        )
        return success
