"""Unit tests for StorageProvider implementations (Local and S3-compatible)."""

import io
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import NotFoundAppException, ValidationAppException
from app.storage.base import StorageMetadata
from app.storage.local import LocalStorageProvider
from app.storage.s3 import S3StorageProvider


@pytest.fixture
def temp_storage_root(tmp_path: Path) -> Path:
    """Create a temporary storage root directory for local storage unit tests."""
    storage_dir = tmp_path / "test_storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest.fixture
def local_provider(temp_storage_root: Path) -> LocalStorageProvider:
    """Provide LocalStorageProvider bound to temp directory."""
    return LocalStorageProvider(base_dir=temp_storage_root)


# ===========================================================================
# 1. LOCAL STORAGE PROVIDER TESTS
# ===========================================================================
@pytest.mark.asyncio
async def test_local_storage_save_and_read_bytes(local_provider: LocalStorageProvider) -> None:
    """Verify persisting and reading bytes via LocalStorageProvider."""
    object_key = "organizations/11111111-1111-1111-1111-111111111111/documents/doc1.txt"
    data = b"Hello, Enterprise AI Analyst storage!"

    meta = await local_provider.save(object_key, data, content_type="text/plain")

    assert isinstance(meta, StorageMetadata)
    assert meta.size == len(data)
    assert meta.content_type == "text/plain"
    assert meta.last_modified is not None

    # Verify exists
    assert await local_provider.exists(object_key) is True

    # Read bytes
    content = await local_provider.read_bytes(object_key)
    assert content == data


@pytest.mark.asyncio
async def test_local_storage_save_stream_and_read_chunks(
    local_provider: LocalStorageProvider,
) -> None:
    """Verify persisting via BinaryIO stream and reading via chunked AsyncIterator."""
    object_key = "organizations/test_org/documents/streamed.bin"
    payload = b"X" * 150000  # > 2 chunks (64KB chunks)

    stream_in = io.BytesIO(payload)
    meta = await local_provider.save(object_key, stream_in, content_type="application/octet-stream")
    assert meta.size == len(payload)

    # Read stream chunks
    reader = await local_provider.read(object_key)
    assert isinstance(reader, AsyncIterator)

    chunks: list[bytes] = []
    async for chunk in reader:
        chunks.append(chunk)

    reconstructed = b"".join(chunks)
    assert reconstructed == payload
    assert len(chunks) >= 2


@pytest.mark.asyncio
async def test_local_storage_delete_and_exists(local_provider: LocalStorageProvider) -> None:
    """Verify deleting stored objects and idempotency."""
    object_key = "organizations/test_org/documents/to_delete.txt"
    await local_provider.save(object_key, b"delete me", content_type="text/plain")

    assert await local_provider.exists(object_key) is True

    # Delete existing
    deleted = await local_provider.delete(object_key)
    assert deleted is True
    assert await local_provider.exists(object_key) is False

    # Delete non-existing returns False
    deleted_again = await local_provider.delete(object_key)
    assert deleted_again is False


@pytest.mark.asyncio
async def test_local_storage_missing_file_raises_not_found(
    local_provider: LocalStorageProvider,
) -> None:
    """Verify reading missing file raises NotFoundAppException."""
    non_existent_key = "organizations/test_org/documents/missing.txt"

    with pytest.raises(NotFoundAppException) as exc_info:
        await local_provider.read_bytes(non_existent_key)
    assert exc_info.value.code == "FILE_NOT_FOUND"

    with pytest.raises(NotFoundAppException) as exc_info2:
        await local_provider.read(non_existent_key)
    assert exc_info2.value.code == "FILE_NOT_FOUND"


@pytest.mark.asyncio
async def test_local_storage_get_metadata(local_provider: LocalStorageProvider) -> None:
    """Verify retrieving metadata without reading file content."""
    object_key = "organizations/test_org/documents/meta_test.txt"
    payload = b"Metadata content"
    await local_provider.save(object_key, payload, content_type="text/plain")

    meta = await local_provider.get_metadata(object_key)
    assert meta is not None
    assert meta.size == len(payload)
    assert meta.last_modified is not None

    # Missing file returns None
    missing_meta = await local_provider.get_metadata("organizations/test_org/documents/absent.txt")
    assert missing_meta is None


# ===========================================================================
# 2. PATH TRAVERSAL DEFENSE TESTS
# ===========================================================================
@pytest.mark.parametrize(
    "malicious_key",
    [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "/etc/shadow",
        "organizations/../../../secret.txt",
        "organizations/test/documents/../../../../boot.ini",
        "/absolute/path/file.pdf",
        "C:\\boot.ini",
    ],
)
def test_path_traversal_attempts_blocked(
    local_provider: LocalStorageProvider, malicious_key: str
) -> None:
    """Assert all path traversal variants are rejected with PATH_TRAVERSAL_DETECTED."""
    with pytest.raises(ValidationAppException) as exc_info:
        local_provider._resolve_safe_path(malicious_key)
    assert exc_info.value.code == "PATH_TRAVERSAL_DETECTED"


def test_empty_object_key_blocked(local_provider: LocalStorageProvider) -> None:
    """Verify empty or dot-only keys are rejected."""
    with pytest.raises(ValidationAppException):
        local_provider._resolve_safe_path("")
    with pytest.raises(ValidationAppException):
        local_provider._resolve_safe_path("   ")


# ===========================================================================
# 3. SECURE OBJECT KEY GENERATION
# ===========================================================================
def test_generate_object_key(local_provider: LocalStorageProvider) -> None:
    """Verify server-generated object key adheres to isolation conventions."""
    org_id = uuid.uuid4()

    key_pdf = local_provider.generate_object_key(org_id, ".pdf")
    key_docx = local_provider.generate_object_key(org_id, "docx")  # handles missing dot

    assert key_pdf.startswith(f"organizations/{org_id}/documents/")
    assert key_pdf.endswith(".pdf")

    assert key_docx.startswith(f"organizations/{org_id}/documents/")
    assert key_docx.endswith(".docx")

    # Verify uniqueness
    key2 = local_provider.generate_object_key(org_id, ".pdf")
    assert key_pdf != key2


# ===========================================================================
# 4. S3-COMPATIBLE STORAGE PROVIDER TESTS (MOCKED CLIENT)
# ===========================================================================
@pytest.mark.asyncio
async def test_s3_storage_provider_with_mock() -> None:
    """Verify S3StorageProvider adapter behavior using mock boto3 client."""
    mock_client = MagicMock()
    mock_client.put_object.return_value = {"ETag": '"abcdef123456"'}
    mock_body = MagicMock()
    mock_body.read.side_effect = [b"mock s3 content", b""]
    mock_client.get_object.return_value = {"Body": mock_body}
    mock_client.head_object.return_value = {
        "ContentLength": 15,
        "ContentType": "text/plain",
        "ETag": '"abcdef123456"',
        "LastModified": None,
    }

    provider = S3StorageProvider(
        bucket="test-bucket",
        client=mock_client,
    )

    # 1. Save
    meta = await provider.save(
        "organizations/org1/documents/doc.txt",
        b"mock s3 content",
        "text/plain",
    )
    assert meta.etag == "abcdef123456"
    assert meta.size == 15
    mock_client.put_object.assert_called_once()

    # 2. Exists
    assert await provider.exists("organizations/org1/documents/doc.txt") is True
    mock_client.head_object.assert_called()

    # 3. Delete
    assert await provider.delete("organizations/org1/documents/doc.txt") is True
    mock_client.delete_object.assert_called_once()
