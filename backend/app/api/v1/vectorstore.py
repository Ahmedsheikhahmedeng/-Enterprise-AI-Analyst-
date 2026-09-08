"""REST API endpoints for vector store health and collection observability."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings, get_settings
from app.db.qdrant import get_qdrant
from app.vectorstore.collection import CollectionManager
from app.vectorstore.health import VectorStoreHealthChecker
from app.vectorstore.schemas import VectorStoreHealthResponse, VectorStoreStatsResponse

router = APIRouter(prefix="/vectorstore", tags=["Vector Store"])


@router.get(
    "/health",
    response_model=VectorStoreHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Vector Store Health Probe",
    description="Inspect connectivity, latency, and active collections in the Qdrant cluster.",
)
async def get_vectorstore_health(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> VectorStoreHealthResponse:
    """Evaluate cluster connectivity and list active vector collections."""
    client: AsyncQdrantClient | None = getattr(request.app.state, "qdrant_client", None)
    return await VectorStoreHealthChecker.check_health(
        client=client,
        url=settings.QDRANT_URL,
    )


@router.get(
    "/collections/{collection_name}",
    response_model=VectorStoreStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Collection Stats",
    description="Inspect points count, dimensions, distance metric, and status for a collection.",
)
async def get_collection_statistics(
    collection_name: str,
    client: Annotated[AsyncQdrantClient, Depends(get_qdrant)],
) -> VectorStoreStatsResponse:
    """Retrieve observability statistics for a specific Qdrant collection."""
    stats = await CollectionManager.get_collection_stats(client, collection_name)
    return VectorStoreStatsResponse(
        collection_name=stats.collection_name,
        points_count=stats.points_count,
        indexed_vectors_count=stats.indexed_vectors_count,
        vector_size=stats.vector_size,
        distance=stats.distance,
        status=stats.status,
    )
