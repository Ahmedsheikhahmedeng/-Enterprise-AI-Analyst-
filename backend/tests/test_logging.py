import logging

from app.core.logging import (
    add_correlation_ids,
    get_logger,
    request_id_ctx_var,
    setup_logging,
    trace_id_ctx_var,
)


def test_add_correlation_ids_injects_contextvars() -> None:
    """Verify processor binds contextvar values to event dictionary."""
    tok_req = request_id_ctx_var.set("req_test_123")
    tok_trace = trace_id_ctx_var.set("trace_test_456")

    try:
        event_dict: dict[str, object] = {"event": "hello"}
        enriched = add_correlation_ids(None, "info", event_dict)
        assert enriched["request_id"] == "req_test_123"
        assert enriched["trace_id"] == "trace_test_456"
    finally:
        request_id_ctx_var.reset(tok_req)
        trace_id_ctx_var.reset(tok_trace)


def test_get_logger_instance() -> None:
    """Verify get_logger returns a bound logger."""
    logger = get_logger("test_module")
    assert logger is not None


def test_setup_logging_json_output() -> None:
    """Verify setup_logging configures root logger without exceptions."""
    setup_logging(log_level="DEBUG", json_format=True)
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) > 0
