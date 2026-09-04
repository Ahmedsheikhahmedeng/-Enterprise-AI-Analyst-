from fastapi import APIRouter

from app.api.v1 import health
from app.auth.router import router as auth_router

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth_router)
