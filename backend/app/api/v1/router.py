from fastapi import APIRouter

from app.api.v1 import health
from app.auth.router import router as auth_router
from app.rbac.router import admin_router, rbac_router
from app.tenancy.router import tenant_router

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(rbac_router)
api_v1_router.include_router(tenant_router)
