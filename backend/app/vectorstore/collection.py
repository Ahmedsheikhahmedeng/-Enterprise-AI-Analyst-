"""Collection management, naming, and payload index orchestration."""

import logging
import re

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PayloadSchemaType,
    SparseIndexParams,
    SparseVectorParams,
    VectorParams,
)

from app.vectorstore.exceptions import CollectionMismatchError, VectorStoreConfigurationError
from app.vectorstore.models import VectorStoreStats

logger = logging.getLogger(__name__)

_SAFE_CHARS = re.compile(r"[^a-zA-Z0-9_]")


def sanitize_identifier(value: str) -> str:
    """Sanitize string into valid alphanumeric and underscore tokens for collection naming."""
    return _SAFE_CHARS.sub("_", value.strip().lower())


def build_collection_name(
    prefix: str,
    provider: str,
    model: str,
    dimensions: int,
    version: str,
) -> str:
    """Construct a deterministic collection name incorporating full embedding identity.

    Guarantees:
    - Vectors of different models, dimensions, or versions can never collide or mix.
    - Resulting name strictly complies with Qdrant collection naming requirements.
    """
    clean_prefix = sanitize_identifier(prefix)
    clean_provider = sanitize_identifier(provider)
    clean_model = sanitize_identifier(model)
    clean_version = sanitize_identifier(version)
    return f"{clean_prefix}__{clean_provider}__{clean_model}__{dimensions}__{clean_version}"


def parse_distance(distance_str: str) -> Distance:
    """Map string distance name to Qdrant Distance enum."""
    dist_map = {
        "cosine": Distance.COSINE,
        "dot": Distance.DOT,
        "euclid": Distance.EUCLID,
        "euclidean": Distance.EUCLID,
    }
    clean = distance_str.strip().lower()
    if clean not in dist_map:
        raise VectorStoreConfigurationError(
            f"Unsupported distance metric: '{distance_str}'. Supported: cosine, dot, euclidean."
        )
    return dist_map[clean]


class CollectionManager:
    """Manages Qdrant collection lifecycles and mandatory payload indexes."""

    PAYLOAD_INDEXES: list[tuple[str, PayloadSchemaType]] = [
        ("organization_id", PayloadSchemaType.KEYWORD),
        ("document_id", PayloadSchemaType.KEYWORD),
        ("chunk_id", PayloadSchemaType.KEYWORD),
        ("chunk_type", PayloadSchemaType.KEYWORD),
        ("page_number", PayloadSchemaType.INTEGER),
        ("embedding_version", PayloadSchemaType.KEYWORD),
    ]

    @classmethod
    async def ensure_collection(
        cls,
        client: AsyncQdrantClient,
        collection_name: str,
        vector_size: int,
        distance: str = "cosine",
        enable_sparse: bool = True,
    ) -> None:
        """Idempotently ensure collection exists with exact dimensions and payload indexes.

        Raises:
            CollectionMismatchError: If collection exists with incompatible dimensions/distance.
        """
        target_distance = parse_distance(distance)

        collections_resp = await client.get_collections()
        existing_names = {c.name for c in collections_resp.collections}

        if collection_name in existing_names:
            # Inspect existing collection parameters
            info = await client.get_collection(collection_name)
            params = info.config.params.vectors
            actual_size: int | None = None
            actual_dist_str: str = ""

            if isinstance(params, VectorParams):
                actual_size = params.size
                actual_dist_str = (
                    params.distance.value
                    if hasattr(params.distance, "value")
                    else str(params.distance)
                )

            target_dist_str = (
                target_distance.value if hasattr(target_distance, "value") else str(target_distance)
            )

            if actual_size is not None and (
                actual_size != vector_size or actual_dist_str.lower() != target_dist_str.lower()
            ):
                raise CollectionMismatchError(
                    collection_name=collection_name,
                    expected_size=vector_size,
                    actual_size=actual_size,
                    expected_distance=target_dist_str,
                    actual_distance=actual_dist_str,
                )
            logger.debug("Collection '%s' already exists and is compatible.", collection_name)
            return

        # Create collection
        logger.info(
            "Creating Qdrant collection '%s' (size=%d, distance=%s, sparse=%s)",
            collection_name,
            vector_size,
            target_distance,
            enable_sparse,
        )
        sparse_config = (
            {"sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))}
            if enable_sparse
            else None
        )
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=target_distance),
            sparse_vectors_config=sparse_config,
        )

        # Create payload indexes
        for field_name, field_type in cls.PAYLOAD_INDEXES:
            try:
                await client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to create payload index for field '%s' on collection '%s': %s",
                    field_name,
                    collection_name,
                    exc,
                )

    @classmethod
    async def get_collection_stats(
        cls,
        client: AsyncQdrantClient,
        collection_name: str,
    ) -> VectorStoreStats:
        """Retrieve point counts and vector configuration statistics."""
        info = await client.get_collection(collection_name)
        params = info.config.params.vectors
        vector_size = 0
        distance_str = "unknown"

        if isinstance(params, VectorParams):
            vector_size = params.size
            distance_str = (
                params.distance.value if hasattr(params.distance, "value") else str(params.distance)
            )

        status_str = info.status.value if hasattr(info.status, "value") else str(info.status)
        points_count = info.points_count or 0
        indexed_count = info.indexed_vectors_count or points_count

        return VectorStoreStats(
            collection_name=collection_name,
            points_count=points_count,
            indexed_vectors_count=indexed_count,
            vector_size=vector_size,
            distance=distance_str,
            status=status_str,
        )

    @classmethod
    async def delete_collection(cls, client: AsyncQdrantClient, collection_name: str) -> bool:
        """Drop collection if it exists."""
        collections_resp = await client.get_collections()
        existing = {c.name for c in collections_resp.collections}
        if collection_name in existing:
            return bool(await client.delete_collection(collection_name))
        return False
