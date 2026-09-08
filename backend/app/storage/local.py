"""Local filesystem storage provider with path traversal defense and atomic writes."""

import os
import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from app.core.exceptions import NotFoundAppException, ValidationAppException
from app.core.logging import get_logger
from app.storage.base import StorageMetadata, StorageProvider

logger = get_logger("storage.local")


class LocalStorageProvider(StorageProvider):
    """Local filesystem implementation of StorageProvider.

    Enforces strict path containment within the configured base directory.
    Rejects any path traversal attempts.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, object_key: str) -> Path:
        """Resolve object key against base directory, preventing path traversal.

        Rejects directory traversal sequences and guarantees that the resolved
        path remains strictly inside base_dir.
        """
        # Guard against traversal patterns
        if ".." in object_key or object_key.startswith("/") or "\\" in object_key:
            logger.warning(
                "Path traversal sequence detected in object key",
                audit_event="path_traversal_blocked",
                object_key=object_key,
            )
            raise ValidationAppException(
                message="Invalid storage object key: path traversal sequence detected.",
                code="PATH_TRAVERSAL_DETECTED",
            )

        cleaned_key = object_key.strip().strip("./\\").strip()
        if not cleaned_key:
            raise ValidationAppException(
                message="Storage object key cannot be empty.",
                code="INVALID_OBJECT_KEY",
            )

        target_path = (self.base_dir / cleaned_key).resolve()

        if not target_path.is_relative_to(self.base_dir):
            logger.warning(
                "Resolved path escapes storage root",
                audit_event="path_traversal_blocked",
                object_key=object_key,
            )
            raise ValidationAppException(
                message="Storage path traversal attempt detected.",
                code="PATH_TRAVERSAL_DETECTED",
            )

        return target_path

    async def save(
        self,
        object_key: str,
        data: BinaryIO | tempfile.SpooledTemporaryFile[bytes] | bytes,
        content_type: str,
    ) -> StorageMetadata:
        """Persist data to local filesystem safely using an atomic temporary file."""
        target_path = self._resolve_safe_path(object_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        total_size = 0
        temp_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                dir=target_path.parent,
                delete=False,
                prefix="tmp_upload_",
            ) as temp_file:
                temp_path = Path(temp_file.name)
                if isinstance(data, bytes):
                    temp_file.write(data)
                    total_size = len(data)
                else:
                    chunk_size = 64 * 1024
                    while True:
                        chunk = data.read(chunk_size)
                        if not chunk:
                            break
                        temp_file.write(chunk)
                        total_size += len(chunk)
                temp_file.flush()
                os.fsync(temp_file.fileno())

            # Atomic replace
            temp_path.replace(target_path)

            stat = target_path.stat()
            last_mod = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

            return StorageMetadata(
                size=total_size,
                content_type=content_type,
                last_modified=last_mod,
            )
        except Exception:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise

    async def read(self, object_key: str) -> AsyncIterator[bytes]:
        """Stream data chunks for given object key."""
        target_path = self._resolve_safe_path(object_key)
        if not target_path.is_file():
            raise NotFoundAppException(
                message="Stored file not found.",
                code="FILE_NOT_FOUND",
            )

        async def _stream() -> AsyncIterator[bytes]:
            chunk_size = 64 * 1024
            with open(target_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

        return _stream()

    async def read_bytes(self, object_key: str) -> bytes:
        """Read complete file content into bytes."""
        target_path = self._resolve_safe_path(object_key)
        if not target_path.is_file():
            raise NotFoundAppException(
                message="Stored file not found.",
                code="FILE_NOT_FOUND",
            )
        with open(target_path, "rb") as f:
            return f.read()

    async def delete(self, object_key: str) -> bool:
        """Delete file from filesystem if it exists."""
        target_path = self._resolve_safe_path(object_key)
        if target_path.is_file():
            target_path.unlink()
            return True
        return False

    async def exists(self, object_key: str) -> bool:
        """Check if file exists on filesystem."""
        try:
            target_path = self._resolve_safe_path(object_key)
            return target_path.is_file()
        except ValidationAppException:
            return False

    async def get_metadata(self, object_key: str) -> StorageMetadata | None:
        """Return file size and last modified timestamp."""
        try:
            target_path = self._resolve_safe_path(object_key)
            if not target_path.is_file():
                return None
            stat = target_path.stat()
            last_mod = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            return StorageMetadata(
                size=stat.st_size,
                content_type="application/octet-stream",
                last_modified=last_mod,
            )
        except ValidationAppException:
            return None
