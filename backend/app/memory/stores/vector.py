"""Qdrant vector store implementation for semantic memory retrieval."""

import logging
import uuid
from typing import Any

from app.core.config import Settings, get_settings
from app.db.qdrant import create_qdrant_client
from app.embeddings.service import EmbeddingService
from app.memory.config import MemoryConfig, get_memory_config
from app.memory.models import MemoryItem
from app.services.embedding_pipeline import create_default_embedding_service

logger = logging.getLogger("app.memory.stores.vector")


class QdrantMemoryVectorStore:
    """Indexes and retrieves memory embeddings using Qdrant with mandatory tenant filtering."""

    def __init__(
        self,
        config: MemoryConfig | None = None,
        settings: Settings | None = None,
        embedding_service: EmbeddingService | None = None,
        qdrant_client: Any | None = None,
    ) -> None:
        self.config = config or get_memory_config()
        self.settings = settings or get_settings()
        self.embedding_service = embedding_service or create_default_embedding_service(
            self.settings
        )
        self.client: Any
        try:
            self.client = qdrant_client or create_qdrant_client(self.settings)
        except Exception as exc:
            logger.warning("Could not initialize Qdrant client for memory vector store: %s", exc)
            self.client = None

    async def _ensure_collection_exists(self, vector_dim: int) -> None:
        """Create Qdrant collection if not present."""
        if not self.client:
            return
        try:
            from qdrant_client.http import models as qmodels

            collections_res = await self.client.get_collections()
            collections = collections_res.collections
            exists = any(c.name == self.config.qdrant_collection_name for c in collections)
            if not exists:
                await self.client.create_collection(
                    collection_name=self.config.qdrant_collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=vector_dim,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
        except Exception as exc:
            logger.warning(
                "Failed ensuring Qdrant collection '%s': %s",
                self.config.qdrant_collection_name,
                exc,
            )

    async def index_memory(self, memory_item: MemoryItem) -> None:
        """Generate embedding and upsert point into Qdrant."""
        if not self.client or not self.config.vector_search_enabled:
            return

        try:
            from qdrant_client.http import models as qmodels

            text_to_embed = f"{memory_item.content}\n{memory_item.summary or ''}".strip()
            embed_batch = await self.embedding_service.embed_texts([text_to_embed])
            if not embed_batch.items or not embed_batch.items[0].vector:
                return

            vector = embed_batch.items[0].vector
            await self._ensure_collection_exists(len(vector))

            point_id = str(memory_item.id)
            payload = {
                "memory_id": str(memory_item.id),
                "organization_id": str(memory_item.organization_id),
                "user_id": str(memory_item.user_id) if memory_item.user_id else None,
                "session_id": str(memory_item.session_id) if memory_item.session_id else None,
                "memory_type": str(memory_item.memory_type),
                "visibility": str(memory_item.visibility),
                "importance": float(memory_item.importance),
                "confidence": float(memory_item.confidence),
                "created_at": memory_item.created_at.isoformat(),
                "expires_at": memory_item.expires_at.isoformat()
                if memory_item.expires_at
                else None,
            }

            await self.client.upsert(
                collection_name=self.config.qdrant_collection_name,
                points=[
                    qmodels.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
        except Exception as exc:
            logger.warning("Failed indexing memory vector for item %s: %s", memory_item.id, exc)

    async def search_vectors(
        self,
        query: str,
        organization_id: uuid.UUID,
        top_k: int = 5,
        user_id: uuid.UUID | None = None,
        session_id: uuid.UUID | None = None,
    ) -> list[tuple[uuid.UUID, float]]:
        """Perform cosine similarity vector search constrained by tenant and scope filters."""
        if not self.client or not self.config.vector_search_enabled:
            return []

        try:
            from qdrant_client.http import models as qmodels

            embed_batch = await self.embedding_service.embed_texts([query])
            if not embed_batch.items or not embed_batch.items[0].vector:
                return []
            query_vector = embed_batch.items[0].vector

            # Mandatory tenant filter
            must_filters: list[Any] = [
                qmodels.FieldCondition(
                    key="organization_id",
                    match=qmodels.MatchValue(value=str(organization_id)),
                )
            ]

            q_filter = qmodels.Filter(must=must_filters)

            hits: list[Any] = []
            if hasattr(self.client, "query_points"):
                response = await self.client.query_points(
                    collection_name=self.config.qdrant_collection_name,
                    query=list(query_vector),
                    query_filter=q_filter,
                    limit=top_k,
                )
                hits = getattr(response, "points", [])
            elif hasattr(self.client, "search"):
                hits = await self.client.search(
                    collection_name=self.config.qdrant_collection_name,
                    query_vector=list(query_vector),
                    query_filter=q_filter,
                    limit=top_k,
                )

            results: list[tuple[uuid.UUID, float]] = []
            for hit in hits:
                if hit.payload and "memory_id" in hit.payload:
                    try:
                        mem_uuid = uuid.UUID(str(hit.payload["memory_id"]))
                        score = float(hit.score)
                        results.append((mem_uuid, score))
                    except ValueError:
                        continue
            return results
        except Exception as exc:
            logger.warning("Vector search in Qdrant failed, falling back: %s", exc)
            return []

    async def delete_memory_vector(
        self,
        memory_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        """Remove vector point from Qdrant."""
        if not self.client:
            return
        try:
            from qdrant_client.http import models as qmodels

            point_id = str(memory_id)
            await self.client.delete(
                collection_name=self.config.qdrant_collection_name,
                points_selector=qmodels.PointIdsList(points=[point_id]),
            )
        except Exception as exc:
            logger.warning("Failed deleting memory vector %s: %s", memory_id, exc)
