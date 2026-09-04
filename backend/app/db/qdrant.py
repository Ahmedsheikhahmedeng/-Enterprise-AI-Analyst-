import asyncio

from fastapi import Request
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("infrastructure.qdrant")


def create_qdrant_client(settings: Settings | None = None) -> AsyncQdrantClient:
    """Create asynchronous Qdrant client configured for vector engine communication."""
    cfg = settings or get_settings()
    logger.info(
        "Creating Qdrant async client",
        url=cfg.QDRANT_URL,
        has_api_key=bool(cfg.QDRANT_API_KEY),
        timeout=cfg.QDRANT_TIMEOUT,
    )
    return AsyncQdrantClient(
        url=cfg.QDRANT_URL,
        api_key=cfg.QDRANT_API_KEY,
        timeout=cfg.QDRANT_TIMEOUT,
        check_compatibility=False,
    )


async def check_qdrant_connectivity(client: AsyncQdrantClient | None, timeout: float = 3.0) -> bool:
    """Execute lightweight probe to verify Qdrant cluster reachability."""
    if client is None:
        return False
    try:
        async with asyncio.timeout(timeout):
            await client.get_collections()
            return True
    except Exception as exc:
        logger.warning("Qdrant connectivity check failed", error=str(exc))
        return False


async def close_qdrant_client(client: AsyncQdrantClient) -> None:
    """Close Qdrant async client transport and connection resources."""
    logger.info("Closing Qdrant async client")
    await client.close()


def get_qdrant(request: Request) -> AsyncQdrantClient:
    """FastAPI dependency providing the active Qdrant client from application state."""
    client: AsyncQdrantClient | None = getattr(request.app.state, "qdrant_client", None)
    if client is None:
        raise RuntimeError("Qdrant client is not initialized on application state.")
    return client
