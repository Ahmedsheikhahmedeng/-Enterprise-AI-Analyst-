import asyncio

from fastapi import Request
from redis.asyncio import Redis, from_url

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("infrastructure.redis")


def create_redis_client(settings: Settings | None = None) -> Redis:
    """Create asynchronous Redis client with configured connection timeout."""
    cfg = settings or get_settings()
    logger.info(
        "Creating Redis client",
        target=cfg.sanitized_redis_url,
        connect_timeout=cfg.REDIS_CONNECT_TIMEOUT,
    )
    return from_url(
        cfg.REDIS_URL,
        socket_connect_timeout=cfg.REDIS_CONNECT_TIMEOUT,
        decode_responses=True,
    )


async def check_redis_connectivity(client: Redis | None, timeout: float = 3.0) -> bool:
    """Execute PING probe to verify Redis reachability."""
    if client is None:
        return False
    try:
        async with asyncio.timeout(timeout):
            pong = await client.ping()
            return bool(pong)
    except Exception as exc:
        logger.warning("Redis connectivity check failed", error=str(exc))
        return False


async def close_redis_client(client: Redis) -> None:
    """Close Redis client connections and release pooled resources."""
    logger.info("Closing Redis client connection pool")
    await client.aclose()


def get_redis(request: Request) -> Redis:
    """FastAPI dependency providing the active Redis client from application state."""
    client: Redis | None = getattr(request.app.state, "redis_client", None)
    if client is None:
        raise RuntimeError("Redis client is not initialized on application state.")
    return client
