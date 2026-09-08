"""Validation utilities for queries, filters, and retrieval parameters."""

import math
import unicodedata
import uuid
from typing import Any

from app.chunking.models import ChunkType
from app.retrieval.config import RetrievalConfig
from app.retrieval.exceptions import (
    InvalidQueryError,
    RetrievalTenantError,
    RetrievalValidationError,
)


class QueryValidator:
    """Validates natural language search queries against security and size guardrails."""

    @classmethod
    def validate_and_clean(
        cls,
        query: str,
        config: RetrievalConfig,
        tokenizer: Any | None = None,
    ) -> tuple[str, int, int]:
        """Validate and normalize query.

        Returns:
            Tuple of (cleaned_query, character_count, token_count).

        Raises:
            InvalidQueryError: If query fails length, token, or empty string checks.
        """
        if not query or not isinstance(query, str):
            raise InvalidQueryError("Query must be a non-empty string.")

        cleaned = unicodedata.normalize("NFC", query).strip()
        char_count = len(cleaned)

        if char_count < config.min_query_characters:
            raise InvalidQueryError(
                f"Query must contain at least {config.min_query_characters} characters.",
                details={"min_characters": config.min_query_characters, "actual": char_count},
            )

        if char_count > config.max_query_characters:
            raise InvalidQueryError(
                f"Query exceeds maximum character limit of {config.max_query_characters}.",
                details={"max_characters": config.max_query_characters, "actual": char_count},
            )

        # Token count calculation
        token_count: int
        if tokenizer is not None and hasattr(tokenizer, "count_tokens"):
            cnt = tokenizer.count_tokens(cleaned)
            token_count = (
                int(cnt) if isinstance(cnt, (int, float)) else max(1, len(cleaned.split()))
            )
        elif tokenizer is not None and hasattr(tokenizer, "tokenize"):
            tokens_list = tokenizer.tokenize(cleaned)
            token_count = (
                len(tokens_list)
                if hasattr(tokens_list, "__len__") and isinstance(len(tokens_list), int)
                else max(1, len(cleaned.split()))
            )
        else:
            # Heuristic token counting: whitespace + punctuation tokens
            token_count = max(1, len(cleaned.split()))

        if token_count > config.max_query_tokens:
            raise InvalidQueryError(
                f"Query exceeds maximum token limit of {config.max_query_tokens} "
                f"(got {token_count} tokens).",
                details={"max_tokens": config.max_query_tokens, "actual": token_count},
            )

        return cleaned, char_count, token_count


class FilterValidator:
    """Validates retrieval filters and operational constraints."""

    @classmethod
    def validate(
        cls,
        organization_id: uuid.UUID,
        top_k: int,
        config: RetrievalConfig,
        chunk_type: str | None = None,
        page_number: int | None = None,
        score_threshold: float | None = None,
    ) -> None:
        """Validate retrieval parameters and filter conditions.

        Raises:
            RetrievalTenantError: If organization_id is missing.
            RetrievalValidationError: If parameters fail constraint checks.
        """
        if not organization_id:
            raise RetrievalTenantError(
                "organization_id is strictly required for retrieval operations."
            )

        if not isinstance(top_k, int) or top_k < 1 or top_k > config.max_top_k:
            raise RetrievalValidationError(
                f"top_k must be an integer between 1 and {config.max_top_k} (got {top_k}).",
                details={"min_top_k": 1, "max_top_k": config.max_top_k, "actual": top_k},
            )

        if page_number is not None and page_number < 1:
            raise RetrievalValidationError(
                f"page_number must be greater than or equal to 1 (got {page_number}).",
                details={"page_number": page_number},
            )

        if chunk_type is not None:
            valid_types = {ct.value for ct in ChunkType}
            if chunk_type.strip().lower() not in valid_types:
                raise RetrievalValidationError(
                    f"Invalid chunk_type '{chunk_type}'. "
                    f"Supported chunk types: {sorted(valid_types)}",
                    details={"chunk_type": chunk_type, "supported": sorted(valid_types)},
                )

        if score_threshold is not None and (
            not isinstance(score_threshold, (int, float)) or not math.isfinite(score_threshold)
        ):
            raise RetrievalValidationError(
                f"score_threshold must be a finite float (got {score_threshold}).",
                details={"score_threshold": score_threshold},
            )
