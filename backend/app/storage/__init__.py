"""Storage layer abstraction and provider factory."""

from app.core.config import Settings, get_settings
from app.storage.base import StorageMetadata, StorageProvider
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider
from app.storage.validation import (
    ALLOWED_EXTENSIONS,
    MIME_TYPE_MAP,
    ProcessedUpload,
    detect_mime_type_from_bytes,
    sanitize_filename,
    validate_and_stream_upload,
)

__all__ = [
    "ALLOWED_EXTENSIONS",
    "LocalStorageProvider",
    "MIME_TYPE_MAP",
    "ProcessedUpload",
    "S3StorageProvider",
    "StorageMetadata",
    "StorageProvider",
    "detect_mime_type_from_bytes",
    "get_storage_provider",
    "sanitize_filename",
    "validate_and_stream_upload",
]


def get_storage_provider(settings: Settings | None = None) -> StorageProvider:
    """Factory returning configured storage provider according to application settings."""
    if settings is None:
        settings = get_settings()

    if settings.STORAGE_BACKEND == "local":
        return LocalStorageProvider(base_dir=settings.LOCAL_STORAGE_ROOT)
    elif settings.STORAGE_BACKEND == "s3":
        return S3StorageProvider(
            bucket=settings.S3_BUCKET,
            endpoint_url=settings.S3_ENDPOINT_URL,
            region=settings.S3_REGION,
            access_key_id=settings.S3_ACCESS_KEY_ID,
            secret_access_key=settings.S3_SECRET_ACCESS_KEY,
        )
    raise ValueError(f"Unsupported storage backend: {settings.STORAGE_BACKEND}")
