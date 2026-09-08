"""Platform route exports."""

from app.api.v1.platform.routes.approvals import approvals_router
from app.api.v1.platform.routes.ask import ask_router
from app.api.v1.platform.routes.executions import executions_router
from app.api.v1.platform.routes.health import admin_router
from app.api.v1.platform.routes.streaming import streaming_router

__all__ = [
    "ask_router",
    "streaming_router",
    "executions_router",
    "approvals_router",
    "admin_router",
]
