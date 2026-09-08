"""Capability and safety validation utilities for LLM generation."""

import json
from typing import Any

from app.llm_gateway.domain.enums import InputTrustLevel, MessageRole, ModelCapability
from app.llm_gateway.domain.errors import (
    CapabilityMismatchError,
    PromptInjectionBoundaryError,
    SchemaSafetyViolationError,
)
from app.llm_gateway.domain.models import LLMMessage, StructuredGenerationRequest


def validate_capabilities(
    model_capabilities: set[ModelCapability],
    required_capabilities: set[ModelCapability],
) -> None:
    """Verify that a candidate model supports all required capabilities."""
    missing = required_capabilities - model_capabilities
    if missing:
        missing_str = ", ".join(m.value for m in missing)
        raise CapabilityMismatchError(f"Model lacks required capabilities: {missing_str}")


def validate_schema_safety(
    schema: dict[str, Any],
    limits: StructuredGenerationRequest,
) -> None:
    """Inspect structured output JSON schema against size, depth, and property limits."""
    schema_str = json.dumps(schema)
    if len(schema_str.encode("utf-8")) > limits.max_schema_bytes:
        raise SchemaSafetyViolationError(
            f"Schema byte size exceeds limit: {len(schema_str.encode('utf-8'))} > {limits.max_schema_bytes}"
        )

    def _inspect_node(node: Any, current_depth: int) -> None:
        if current_depth > limits.max_nesting_depth:
            raise SchemaSafetyViolationError(
                f"Schema nesting depth exceeds limit: {current_depth} > {limits.max_nesting_depth}"
            )
        if isinstance(node, dict):
            properties = node.get("properties", {})
            if isinstance(properties, dict) and len(properties) > limits.max_properties:
                raise SchemaSafetyViolationError(
                    f"Schema property count exceeds limit: {len(properties)} > {limits.max_properties}"
                )
            enums = node.get("enum", [])
            if isinstance(enums, list) and len(enums) > limits.max_enum_size:
                raise SchemaSafetyViolationError(
                    f"Schema enum size exceeds limit: {len(enums)} > {limits.max_enum_size}"
                )
            for val in node.values():
                _inspect_node(val, current_depth + 1)
        elif isinstance(node, list):
            for item in node:
                _inspect_node(item, current_depth + 1)

    _inspect_node(schema, 1)


def enforce_trust_boundaries(messages: list[LLMMessage]) -> list[LLMMessage]:
    """Ensure non-system content cannot be disguised as system instructions."""
    sanitized: list[LLMMessage] = []
    for msg in messages:
        if msg.role == MessageRole.SYSTEM and msg.trust_level != InputTrustLevel.SYSTEM_INSTRUCTION:
            raise PromptInjectionBoundaryError(
                f"Untrusted input trust level '{msg.trust_level.value}' cannot be assigned to SYSTEM role."
            )
        sanitized.append(msg)
    return sanitized
