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
from app.retrieval.service import DenseRetrievalService
from app.vectorstore.config import VectorStoreConfig
from app.vectorstore.providers.qdrant import QdrantVectorStoreProvider
from app.vectorstore.service import VectorStoreService


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

    if getattr(app.state, "vector_store_service", None) is None:
        client = getattr(app.state, "qdrant_client", None)
        if client is not None:
            vs_config = VectorStoreConfig.from_settings(settings)
            provider = QdrantVectorStoreProvider(client=client, config=vs_config)
            app.state.vector_store_provider = provider
            app.state.vector_store_service = VectorStoreService(config=vs_config, provider=provider)

    if getattr(app.state, "dense_retrieval_service", None) is None:
        vs_svc = getattr(app.state, "vector_store_service", None)
        if vs_svc is not None:
            emb_svc = getattr(app.state, "embedding_service", None)
            if emb_svc is None:
                from app.services.embedding_pipeline import create_default_embedding_service

                redis_cli = getattr(app.state, "redis_client", None)
                emb_svc = create_default_embedding_service(
                    settings=settings, redis_client=redis_cli
                )
                app.state.embedding_service = emb_svc
            app.state.dense_retrieval_service = DenseRetrievalService(
                embedding_service=emb_svc,
                vector_store_service=vs_svc,
            )

    if getattr(app.state, "reranker_service", None) is None and settings.RERANKING_ENABLED:
        from app.reranking.config import get_reranker_config
        from app.reranking.service import CrossEncoderRerankingService

        app.state.reranker_service = CrossEncoderRerankingService(config=get_reranker_config())

    if getattr(app.state, "hybrid_retrieval_service", None) is None:
        dense_svc = getattr(app.state, "dense_retrieval_service", None)
        vs_svc = getattr(app.state, "vector_store_service", None)
        if dense_svc is not None and vs_svc is not None:
            from app.retrieval.hybrid.service import HybridRetrievalService
            from app.retrieval.sparse.service import SparseRetrievalService

            sparse_svc = SparseRetrievalService(
                vector_store_service=vs_svc,
                embedding_service=getattr(app.state, "embedding_service", None),
            )
            app.state.sparse_retrieval_service = sparse_svc
            reranker_svc = getattr(app.state, "reranker_service", None)

            qu_svc = None
            if settings.QUERY_UNDERSTANDING_ENABLED:
                from app.query.config import get_query_understanding_config
                from app.query.service import QueryUnderstandingService

                qu_svc = QueryUnderstandingService(config=get_query_understanding_config())
                app.state.query_understanding_service = qu_svc

            hybrid_svc = HybridRetrievalService(
                dense_service=dense_svc,
                sparse_service=sparse_svc,
                reranker_service=reranker_svc,
                query_understanding_service=qu_svc,
            )
            if qu_svc is not None:
                from app.query.multi_retrieval import MultiQueryRetrievalService

                mq_svc = MultiQueryRetrievalService(
                    hybrid_service=hybrid_svc,
                    reranker_service=reranker_svc,
                )
                hybrid_svc.multi_query_service = mq_svc
                app.state.multi_query_service = mq_svc

            app.state.hybrid_retrieval_service = hybrid_svc

    if getattr(app.state, "rag_service", None) is None and settings.RAG_ENABLED:
        rag_hybrid_svc = getattr(app.state, "hybrid_retrieval_service", None)
        if rag_hybrid_svc is not None:
            from app.rag.config import get_rag_config
            from app.rag.service import RAGService

            app.state.rag_service = RAGService(
                hybrid_retrieval_service=rag_hybrid_svc,
                query_understanding_service=getattr(app.state, "query_understanding_service", None),
                config=get_rag_config(),
            )

    if getattr(app.state, "sql_agent_service", None) is None and settings.SQL_AGENT_ENABLED:
        from app.sql_agent.config import get_sql_agent_config
        from app.sql_agent.service import SQLAgentService

        app.state.sql_agent_service = SQLAgentService(
            config=get_sql_agent_config(),
        )

    if getattr(app.state, "analyst_service", None) is None and settings.ANALYST_ENABLED:
        sql_svc = getattr(app.state, "sql_agent_service", None)
        rag_svc = getattr(app.state, "rag_service", None)
        if sql_svc is not None and rag_svc is not None:
            from app.analyst.config import get_analyst_config
            from app.analyst.service import AIAnalystService

            app.state.analyst_service = AIAnalystService(
                sql_service=sql_svc,
                rag_service=rag_svc,
                config=get_analyst_config(),
            )

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
    from app.observability.middleware import ObservabilityMiddleware
    from app.security.cors import get_hardened_cors_kwargs
    from app.security.headers import SecurityHeadersMiddleware

    fastapi_app.add_middleware(SecurityHeadersMiddleware)
    fastapi_app.add_middleware(ObservabilityMiddleware)
    fastapi_app.add_middleware(CorrelationIdMiddleware)

    # 2. Register CORS Middleware with hardened options
    cors_kwargs = get_hardened_cors_kwargs(
        allowed_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
    )
    fastapi_app.add_middleware(CORSMiddleware, **cors_kwargs)

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
