import asyncio
from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings
from app.db.postgres import check_database_connectivity
from app.db.qdrant import check_qdrant_connectivity
from app.db.redis import check_redis_connectivity
from app.schemas.health import (
    DependencyStatus,
    HealthResponse,
    LivenessResponse,
    ReadinessResponse,
)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Basic Service Health",
    description="Returns static service identifier and active version for basic pinging.",
)
async def get_health() -> HealthResponse:
    """Return backward-compatible baseline service health status."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="enterprise-ai-analyst",
        version=settings.APP_VERSION,
    )


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Liveness Probe",
    description="Process liveness probe indicating whether the FastAPI process is responsive.",
)
async def get_liveness() -> LivenessResponse:
    """Liveness probe verifying the application loop is processing requests."""
    return LivenessResponse(
        status="ok",
        service="enterprise-ai-analyst",
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Service Readiness Probe",
    description=(
        "Deep infrastructure readiness probe verifying PostgreSQL, Redis, and Qdrant connectivity. "
        "Returns 200 OK when all infrastructure services are reachable, or 503 Service Unavailable "
        "if any dependency is offline."
    ),
    responses={
        status.HTTP_200_OK: {"model": ReadinessResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse},
    },
)
async def get_readiness(request: Request, response: Response) -> ReadinessResponse:
    """Readiness probe evaluating health of backing infrastructure."""
    engine = getattr(request.app.state, "db_engine", None)
    redis_client = getattr(request.app.state, "redis_client", None)
    qdrant_client = getattr(request.app.state, "qdrant_client", None)

    db_ok, redis_ok, qdrant_ok = await asyncio.gather(
        check_database_connectivity(engine),
        check_redis_connectivity(redis_client),
        check_qdrant_connectivity(qdrant_client),
    )

    is_ready = db_ok and redis_ok and qdrant_ok
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ok" if is_ready else "unhealthy",
        service="enterprise-ai-analyst",
        dependencies=DependencyStatus(
            postgresql="ok" if db_ok else "unavailable",
            redis="ok" if redis_ok else "unavailable",
            qdrant="ok" if qdrant_ok else "unavailable",
        ),
    )


@router.get(
    "/health/dependencies",
    status_code=status.HTTP_200_OK,
    summary="Granular Dependencies Health",
    description="Returns detailed per-dependency status and probe latencies without bringing down unaffected routes.",
)
async def get_dependencies_health(request: Request) -> dict[str, Any]:
    """Granular dependency health inspection."""
    from app.observability.health import get_health_checker

    engine = getattr(request.app.state, "db_engine", None)
    redis_client = getattr(request.app.state, "redis_client", None)
    qdrant_client = getattr(request.app.state, "qdrant_client", None)

    checker = get_health_checker()
    return await checker.check_dependencies(
        db_engine=engine,
        redis_client=redis_client,
        qdrant_client=qdrant_client,
    )
