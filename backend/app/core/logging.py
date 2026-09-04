import logging
import sys
from contextvars import ContextVar
from typing import cast

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

# Context variables for request and distributed trace tracking across async lifecycles
request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")
trace_id_ctx_var: ContextVar[str] = ContextVar("trace_id", default="")


def add_correlation_ids(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Inject request_id and trace_id from async contextvars into log event."""
    req_id = request_id_ctx_var.get()
    trace_id = trace_id_ctx_var.get()
    if req_id:
        event_dict["request_id"] = req_id
    if trace_id:
        event_dict["trace_id"] = trace_id
    return event_dict


def setup_logging(log_level: str = "INFO", json_format: bool = True) -> None:
    """Configure structlog and standard logging with structured JSON formatting."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        add_correlation_ids,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    formatter_processor: Processor
    if json_format:
        formatter_processor = structlog.processors.JSONRenderer()
    else:
        formatter_processor = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure root standard library handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=formatter_processor,
            foreign_pre_chain=shared_processors,
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)

    # Silence overly verbose third-party loggers
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "asyncio"):
        logging.getLogger(logger_name).handlers.clear()
        logging.getLogger(logger_name).propagate = True


def get_logger(name: str = "app") -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger instance."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
