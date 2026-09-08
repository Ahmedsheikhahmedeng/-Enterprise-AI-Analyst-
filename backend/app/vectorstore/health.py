"""Health and connectivity probes for the vector store subsystem."""

import logging
import time

from qdrant_client import AsyncQdrantClient

from app.vectorstore.schemas import VectorStoreHealthResponse

logger = logging.getLogger(__name__)


class VectorStoreHealthChecker:
    """Evaluates connectivity and operational status of the vector store cluster."""

    @classmethod
    async def check_health(
        cls,
        client: AsyncQdrantClient | None,
        url: str,
    ) -> VectorStoreHealthResponse:
        """Probe Qdrant cluster and return latency and collection listings."""
        if client is None:
            return VectorStoreHealthResponse(
                status="unhealthy",
                collections=[],
                url=url,
                latency_ms=0.0,
            )

        start = time.perf_counter()
        try:
            resp = await client.get_collections()
            duration_ms = (time.perf_counter() - start) * 1000.0
            names = [c.name for c in resp.collections]
            return VectorStoreHealthResponse(
                status="ok",
                collections=names,
                url=url,
                latency_ms=duration_ms,
            )
        except Exception as exc:
            logger.warning("Vector store health probe failed: %s", exc)
            return VectorStoreHealthResponse(
                status="unhealthy",
                collections=[],
                url=url,
                latency_ms=(time.perf_counter() - start) * 1000.0,
            )
