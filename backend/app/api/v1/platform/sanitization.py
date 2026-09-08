"""Event Payload Security & Sanitization Engine — TASK 34.

Strictly prevents leakage of credentials, passwords, raw prompts,
private system instructions, and internal stack traces into client-facing SSE streams.
"""

import re
from typing import Any

from app.observability.redaction import TelemetryRedactor

_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(secret|password|passwd|api[_-]?key|token|auth|bearer|credential|"
    r"prompt|instruction|system_message|stack_trace|traceback|exc_info)",
    re.IGNORECASE,
)

_telemetry_redactor = TelemetryRedactor()


def sanitize_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Recursively scrub sensitive keys and text from an event payload before SSE dispatch."""
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        # 1. Filter out sensitive keys completely or mask them
        if _SENSITIVE_KEY_PATTERNS.search(str(key)):
            continue

        # 2. Recursively sanitize nested structures
        if isinstance(value, dict):
            sanitized[key] = sanitize_event_payload(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_event_payload(item) if isinstance(item, dict) else _sanitize_scalar(item)
                for item in value
            ]
        else:
            sanitized[key] = _sanitize_scalar(value)

    return sanitized


def _sanitize_scalar(value: Any) -> Any:
    """Sanitize scalar values (strings, numbers, booleans)."""
    if isinstance(value, str):
        # Scrub credentials or token-like patterns from string contents
        return _telemetry_redactor.redact_text(value)
    return value
