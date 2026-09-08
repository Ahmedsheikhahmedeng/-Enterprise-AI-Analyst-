"""S3-compatible storage provider adapter (AWS S3, MinIO, Cloudflare R2)."""

import tempfile
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, BinaryIO

from app.core.exceptions import InternalAppException, NotFoundAppException
from app.core.logging import get_logger
from app.storage.base import StorageMetadata, StorageProvider

logger = get_logger("storage.s3")


class S3StorageProvider(StorageProvider):
    """S3-compatible object storage provider adapter.

    Enforces private bucket access, server-side access only, and no public URLs.
    Supports AWS S3, MinIO, and Cloudflare R2 via standard S3 API conventions.
    """

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client: Any = None,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self._client = client

    def _get_client(self) -> Any:
        """Lazily initialize S3 client if not explicitly injected."""
        if self._client is not None:
            return self._client

        try:
            import boto3  # type: ignore[import-not-found]
            from botocore.config import Config  # type: ignore[import-not-found]
        except ImportError as exc:
            logger.error("boto3 is not installed. S3 storage provider cannot be initialized.")
            raise InternalAppException(
                message="S3 storage provider dependencies (boto3) are not installed.",
                code="STORAGE_PROVIDER_ERROR",
            ) from exc

        client_kwargs: dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.region,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "config": Config(signature_version="s3v4"),
        }
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        self._client = boto3.client(**client_kwargs)
        return self._client

    async def save(
        self,
        object_key: str,
        data: BinaryIO | tempfile.SpooledTemporaryFile[bytes] | bytes,
        content_type: str,
    ) -> StorageMetadata:
        """Upload object to private S3 bucket."""
        client = self._get_client()
        body = data if isinstance(data, bytes) else data.read()
        size = len(body)

        try:
            response = client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=body,
                ContentType=content_type,
            )
            etag = response.get("ETag", "").strip('"')
            return StorageMetadata(
                size=size,
                content_type=content_type,
                etag=etag,
                last_modified=datetime.now(UTC),
            )
        except Exception as exc:
            logger.error(
                "S3 upload failed",
                bucket=self.bucket,
                object_key=object_key,
                error=str(exc),
            )
            raise InternalAppException(
                message="Failed to persist file in S3 storage.",
                code="STORAGE_ERROR",
            ) from exc

    async def read(self, object_key: str) -> AsyncIterator[bytes]:
        """Stream chunks from S3 object."""
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self.bucket, Key=object_key)
            stream = response["Body"]

            async def _generator() -> AsyncIterator[bytes]:
                chunk_size = 64 * 1024
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

            return _generator()
        except Exception as exc:
            if "NoSuchKey" in str(exc) or "404" in str(exc):
                raise NotFoundAppException(
                    message="Requested object not found in storage.",
                    code="FILE_NOT_FOUND",
                ) from exc
            raise InternalAppException(
                message="Failed to retrieve object from S3 storage.",
                code="STORAGE_ERROR",
            ) from exc

    async def read_bytes(self, object_key: str) -> bytes:
        """Read complete bytes for S3 object."""
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self.bucket, Key=object_key)
            content: bytes = response["Body"].read()
            return content
        except Exception as exc:
            if "NoSuchKey" in str(exc) or "404" in str(exc):
                raise NotFoundAppException(
                    message="Requested object not found in storage.",
                    code="FILE_NOT_FOUND",
                ) from exc
            raise InternalAppException(
                message="Failed to read object from S3 storage.",
                code="STORAGE_ERROR",
            ) from exc

    async def delete(self, object_key: str) -> bool:
        """Delete object from S3 bucket."""
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket, Key=object_key)
            return True
        except Exception as exc:
            logger.error(
                "S3 delete failed",
                bucket=self.bucket,
                object_key=object_key,
                error=str(exc),
            )
            return False

    async def exists(self, object_key: str) -> bool:
        """Check whether object exists via head_object."""
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket, Key=object_key)
            return True
        except Exception:
            return False

    async def get_metadata(self, object_key: str) -> StorageMetadata | None:
        """Retrieve object metadata via head_object without reading content."""
        client = self._get_client()
        try:
            response = client.head_object(Bucket=self.bucket, Key=object_key)
            return StorageMetadata(
                size=response.get("ContentLength", 0),
                content_type=response.get("ContentType", "application/octet-stream"),
                etag=response.get("ETag", "").strip('"'),
                last_modified=response.get("LastModified"),
            )
        except Exception:
            return None
