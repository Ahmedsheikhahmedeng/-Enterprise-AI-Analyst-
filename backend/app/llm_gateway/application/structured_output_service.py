"""Structured output parsing, Pydantic validation, and JSON schema safety enforcement."""

import json
import logging
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm_gateway.domain.capabilities import validate_schema_safety
from app.llm_gateway.domain.errors import StructuredOutputValidationError
from app.llm_gateway.domain.models import StructuredGenerationRequest

logger = logging.getLogger(__name__)


class StructuredOutputService:
    """Validates JSON schemas and parses structured LLM generation payloads."""

    def prepare_structured_request(
        self,
        schema: dict[str, Any] | None = None,
        pydantic_model: type[BaseModel] | None = None,
        strict: bool = True,
    ) -> StructuredGenerationRequest:
        """Construct and validate structured generation request bounds."""
        target_schema = schema or {}
        if pydantic_model is not None and not target_schema:
            target_schema = pydantic_model.model_json_schema()

        req = StructuredGenerationRequest(
            schema=target_schema,
            pydantic_model=pydantic_model,
            strict=strict,
        )
        if target_schema:
            validate_schema_safety(target_schema, req)
        return req

    def validate_and_parse(
        self,
        content: str,
        structured_req: StructuredGenerationRequest,
    ) -> tuple[dict[str, Any], BaseModel | None]:
        """Parse content to JSON and validate against schema or Pydantic model."""
        content_clean = content.strip()
        # Strip markdown json code blocks if present
        if content_clean.startswith("```json"):
            content_clean = content_clean[7:]
        elif content_clean.startswith("```"):
            content_clean = content_clean[3:]
        if content_clean.endswith("```"):
            content_clean = content_clean[:-3]
        content_clean = content_clean.strip()

        try:
            parsed = json.loads(content_clean)
        except Exception as exc:
            raise StructuredOutputValidationError(f"Response is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise StructuredOutputValidationError(
                f"Expected JSON object, got {type(parsed).__name__}"
            )

        model_instance: BaseModel | None = None
        if structured_req.pydantic_model is not None:
            try:
                model_instance = structured_req.pydantic_model.model_validate(parsed)
            except ValidationError as exc:
                raise StructuredOutputValidationError(
                    f"Structured output failed Pydantic validation: {exc}"
                ) from exc

        return parsed, model_instance
