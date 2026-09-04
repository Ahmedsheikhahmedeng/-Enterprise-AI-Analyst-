import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.db.postgres import (
    check_database_connectivity,
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.db.qdrant import (
    check_qdrant_connectivity,
    close_qdrant_client,
    create_qdrant_client,
)
from app.db.redis import (
    check_redis_connectivity,
    close_redis_client,
    create_redis_client,
)


async def _verify_startup_connectivity(app: FastAPI, settings: Settings) -> None:
    """Perform bounded retry connectivity probe during startup lifecycle."""
    logger = get_logger("startup.probe")
    max_retries = settings.INFRASTRUCTURE_STARTUP_RETRIES
    delay = settings.INFRASTRUCTURE_RETRY_DELAY

    for attempt in range(1, max_retries + 1):
        engine = getattr(app.state, "db_engine", None)
        redis_cli = getattr(app.state, "redis_client", None)
        qdrant_cli = getattr(app.state, "qdrant_client", None)

        db_ok = await check_database_connectivity(engine) if engine else False
        redis_ok = await check_redis_connectivity(redis_cli) if redis_cli else False
        qdrant_ok = await check_qdrant_connectivity(qdrant_cli) if qdrant_cli else False

        if db_ok and redis_ok and qdrant_ok:
            logger.info(
                "All infrastructure dependencies verified and reachable",
                attempt=attempt,
                postgres="ok",
                redis="ok",
                qdrant="ok",
            )
            return

        logger.warning(
            "Infrastructure dependencies not fully reachable",
            attempt=attempt,
            max_retries=max_retries,
            postgres="ok" if db_ok else "unreachable",
            redis="ok" if redis_ok else "unreachable",
            qdrant="ok" if qdrant_ok else "unreachable",
        )

        if attempt < max_retries:
            await asyncio.sleep(delay)

    if settings.is_production:
        raise RuntimeError(
            "Production startup aborted: required backing infrastructure is unreachable."
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan context managing startup connections and shutdown disposal."""
    settings = get_settings()
    setup_logging(log_level=settings.LOG_LEVEL, json_format=not settings.DEBUG)
    logger = get_logger("main")
    logger.info(
        "Application startup initialized",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # 1. Initialize PostgreSQL Engine & Session Factory if not pre-injected
    if getattr(app.state, "db_engine", None) is None and not settings.is_testing:
        engine = create_database_engine(settings)
        app.state.db_engine = engine
        app.state.db_session_factory = create_session_factory(engine)
    elif (
        getattr(app.state, "db_engine", None) is not None
        and getattr(app.state, "db_session_factory", None) is None
    ):
        app.state.db_session_factory = create_session_factory(app.state.db_engine)

    # 2. Initialize Redis client if not pre-injected
    if getattr(app.state, "redis_client", None) is None and not settings.is_testing:
        app.state.redis_client = create_redis_client(settings)

    # 3. Initialize Qdrant client if not pre-injected
    if getattr(app.state, "qdrant_client", None) is None and not settings.is_testing:
        app.state.qdrant_client = create_qdrant_client(settings)

    # 4. Verify connectivity with retry loop if not in unit testing
    if not settings.is_testing:
        await _verify_startup_connectivity(app, settings)

    yield

    # 5. Graceful Resource Disposal
    logger.info("Application shutdown initiated: releasing infrastructure connections")

    if getattr(app.state, "redis_client", None) is not None:
        try:
            await close_redis_client(app.state.redis_client)
        except Exception as exc:
            logger.warning("Error closing Redis client during shutdown", error=str(exc))

    if getattr(app.state, "qdrant_client", None) is not None:
        try:
            await close_qdrant_client(app.state.qdrant_client)
        except Exception as exc:
            logger.warning("Error closing Qdrant client during shutdown", error=str(exc))

    if getattr(app.state, "db_engine", None) is not None:
        try:
            await dispose_database_engine(app.state.db_engine)
        except Exception as exc:
            logger.warning("Error disposing DB engine during shutdown", error=str(exc))

    logger.info("Application shutdown completed cleanly")


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
