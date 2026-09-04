from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Returns service availability status, identifier, and active release version.",
)
async def get_health() -> HealthResponse:
    """Return static health status for the foundation stage."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="enterprise-ai-analyst",
        version=settings.APP_VERSION,
    )
