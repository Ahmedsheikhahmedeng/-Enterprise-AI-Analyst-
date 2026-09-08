"""E2E Test: API, SSE, and Correlation Contract Suite."""

from app.product.contracts import ProductContractValidator


def test_canonical_error_contract_valid() -> None:
    payload = {
        "error": {
            "code": "BUDGET_EXCEEDED",
            "message": "Monthly cost budget of $500.00 exhausted.",
            "request_id": "req-1234-abcd",
            "details": {"limit": 500.0, "current": 500.12},
        }
    }
    result = ProductContractValidator.validate_error_contract(400, payload)
    assert result.is_valid is True
    assert len(result.violations) == 0


def test_canonical_error_contract_missing_error_key() -> None:
    payload = {"message": "Something went wrong"}
    result = ProductContractValidator.validate_error_contract(500, payload)
    assert result.is_valid is False
    assert any("missing top-level 'error' key" in v for v in result.violations)


def test_canonical_error_contract_invalid_code_format() -> None:
    payload = {
        "error": {
            "code": "invalidCode-format",
            "message": "Bad error code",
        }
    }
    result = ProductContractValidator.validate_error_contract(400, payload)
    assert result.is_valid is False
    assert any("violates UPPER_SNAKE_CASE format" in v for v in result.violations)


def test_sse_stream_contract_valid() -> None:
    events = [
        {"event": "start", "data": {"session_id": "sess_1"}},
        {"event": "chunk", "data": {"text": "Hello"}},
        {"event": "chunk", "data": {"text": " world"}},
        {"event": "done", "data": {"total_tokens": 15}},
    ]
    result = ProductContractValidator.validate_sse_stream_contract(events)
    assert result.is_valid is True
    assert len(result.violations) == 0


def test_sse_stream_contract_missing_terminal() -> None:
    events = [
        {"event": "start", "data": {"session_id": "sess_1"}},
        {"event": "chunk", "data": {"text": "Hello"}},
    ]
    result = ProductContractValidator.validate_sse_stream_contract(events)
    assert result.is_valid is False
    assert any("without a terminal event" in v for v in result.violations)


def test_correlation_header_contract() -> None:
    valid_headers = {"X-Request-ID": "req-999-xyz", "Content-Type": "application/json"}
    assert ProductContractValidator.validate_correlation_contract(valid_headers).is_valid is True

    missing_headers = {"Content-Type": "application/json"}
    assert ProductContractValidator.validate_correlation_contract(missing_headers).is_valid is False
