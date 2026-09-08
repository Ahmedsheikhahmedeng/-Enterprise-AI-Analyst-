"""Vector embedding generation and indexing for Semantic Catalog concepts."""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.embeddings.service import EmbeddingService
from app.models.semantic import SemanticEmbedding
from app.services.embedding_pipeline import create_default_embedding_service
from app.vectorstore.models import VectorPoint
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider

logger = logging.getLogger("semantic.embedding")

SEMANTIC_COLLECTION_NAME = "semantic_catalog"


class SemanticEmbeddingService:
    """Manages vector representation of semantic definitions and Qdrant synchronization."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantVectorStoreProvider | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def _get_embedding_service(self) -> EmbeddingService:
        if self.embedding_service is None:
            self.embedding_service = create_default_embedding_service()
        return self.embedding_service

    async def index_semantic_object(
        self,
        organization_id: uuid.UUID,
        semantic_object_type: str,
        semantic_object_id: uuid.UUID,
        text_to_embed: str,
        session: AsyncSession,
        language: str = "en",
        version: int = 1,
    ) -> str | None:
        """Generate embedding vector and store payload in Qdrant and database."""
        try:
            emb_svc = self._get_embedding_service()
            vector = await emb_svc.embed_query(text_to_embed)
            if not vector:
                return None

            vector_id = uuid.uuid4()

            # Optional Qdrant indexing if vector store available
            if self.vector_store is not None:
                point = VectorPoint(
                    id=vector_id,
                    vector=vector,
                    payload={
                        "organization_id": str(organization_id),
                        "semantic_object_type": semantic_object_type,
                        "semantic_object_id": str(semantic_object_id),
                        "language": language,
                        "version": version,
                        "text": text_to_embed[:1000],
                    },
                )
                try:
                    await self.vector_store.upsert(
                        collection_name=SEMANTIC_COLLECTION_NAME,
                        points=[point],
                    )
                except Exception as exc:
                    logger.debug("Qdrant upsert skipped: %s", exc)

            # Record embedding metadata in database
            db_emb = SemanticEmbedding(
                id=uuid.uuid4(),
                organization_id=organization_id,
                semantic_object_type=semantic_object_type,
                semantic_object_id=semantic_object_id,
                vector_id=str(vector_id),
                embedding_model=emb_svc.model_name,
                embedding_version="v1.0",
                status="completed",
            )
            session.add(db_emb)
            await session.flush()
            return str(vector_id)
        except Exception as exc:
            logger.warning("Failed to embed semantic object %s: %s", semantic_object_id, exc)
            return None
