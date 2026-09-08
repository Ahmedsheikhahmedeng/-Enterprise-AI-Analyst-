"""Abstract storage provider and metadata definitions for document management."""

import tempfile
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO


@dataclass(frozen=True)
class StorageMetadata:
    """Metadata describing a stored object in a storage provider."""

    size: int
    content_type: str
    etag: str | None = None
    last_modified: datetime | None = None


class StorageProvider(ABC):
    """Abstract base class defining the contract for all storage providers."""

    @abstractmethod
    async def save(
        self,
        object_key: str,
        data: BinaryIO | tempfile.SpooledTemporaryFile[bytes] | bytes,
        content_type: str,
    ) -> StorageMetadata:
        """Persist data under the specified object key."""
        pass

    @abstractmethod
    async def read(self, object_key: str) -> AsyncIterator[bytes]:
        """Stream chunks of data for the given object key."""
        pass

    @abstractmethod
    async def read_bytes(self, object_key: str) -> bytes:
        """Read complete data bytes for the given object key."""
        pass

    @abstractmethod
    async def delete(self, object_key: str) -> bool:
        """Delete object from storage. Return True if deleted, False if not found."""
        pass

    @abstractmethod
    async def exists(self, object_key: str) -> bool:
        """Check whether object key exists in storage."""
        pass

    @abstractmethod
    async def get_metadata(self, object_key: str) -> StorageMetadata | None:
        """Retrieve metadata for stored object without reading body."""
        pass

    def generate_object_key(self, organization_id: uuid.UUID, file_extension: str) -> str:
        """Generate a server-controlled, cryptographically random object key.

        Never includes untrusted user inputs or original filenames in the key path.
        Example output: organizations/<organization_id>/documents/<uuid>.<ext>
        """
        clean_ext = file_extension.lower()
        if clean_ext and not clean_ext.startswith("."):
            clean_ext = f".{clean_ext}"
        object_uuid = uuid.uuid4()
        return f"organizations/{organization_id}/documents/{object_uuid}{clean_ext}"
