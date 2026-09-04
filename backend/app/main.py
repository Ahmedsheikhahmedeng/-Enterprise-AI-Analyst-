from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context for startup and shutdown hooks."""
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, json_format=not settings.DEBUG)
    logger = get_logger("main")
    logger.info(
        "Application startup initialized",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )
    yield
    logger.info("Application shutdown completed")


def create_app() -> FastAPI:
    """Application factory for Enterprise AI Analyst backend."""
    settings = get_settings()

    fastapi_app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Enterprise AI intelligence platform connecting structured and unstructured "
            "business data with LLM-powered reasoning, RAG, Text-to-SQL, and evidence verification."
        ),
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # 1. Register Core Middlewares
    fastapi_app.add_middleware(CorrelationIdMiddleware)

    # 2. Register CORS Middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Trace-ID"],
    )

    # 3. Register Global Exception Handlers
    fastapi_app.add_exception_handler(AppException, app_exception_handler)  # type: ignore[arg-type]
    fastapi_app.add_exception_handler(
        StarletteHTTPException,
        http_exception_handler,  # type: ignore[arg-type]
    )
    fastapi_app.add_exception_handler(
        RequestValidationError,
        validation_exception_handler,  # type: ignore[arg-type]
    )
    fastapi_app.add_exception_handler(Exception, unhandled_exception_handler)

    # 4. Include API Routers
    fastapi_app.include_router(api_router)

    return fastapi_app


app = create_app()
