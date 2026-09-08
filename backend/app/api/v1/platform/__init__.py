"""Platform module root router bundling all production frontend API routes — TASK 34."""

from fastapi import APIRouter

from app.api.v1.platform.routes.approvals import approvals_router
from app.api.v1.platform.routes.ask import ask_router
from app.api.v1.platform.routes.executions import executions_router
from app.api.v1.platform.routes.health import admin_router, platform_health_router
from app.api.v1.platform.routes.streaming import streaming_router

platform_router = APIRouter()
platform_router.include_router(ask_router)
platform_router.include_router(streaming_router)
platform_router.include_router(executions_router)
platform_router.include_router(approvals_router)
platform_router.include_router(admin_router)
platform_router.include_router(platform_health_router)

__all__ = ["platform_router"]
