"""Normalization service for tabular identifiers and values."""

import re
import unicodedata
from typing import Any

from app.ingestion.domain.enums import ColumnDataType
from app.ingestion.domain.models import ColumnDefinition


class NormalizationService:
    """Normalizes column names and values for safe relational storage and SQL generation."""

    RESERVED_SQL_WORDS = {
        "select",
        "from",
        "where",
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "table",
        "index",
        "view",
        "join",
        "inner",
        "outer",
        "left",
        "right",
        "group",
        "by",
        "order",
        "having",
        "limit",
        "offset",
        "union",
        "all",
        "distinct",
        "case",
        "when",
        "then",
        "else",
        "end",
        "and",
        "or",
        "not",
        "null",
        "is",
        "in",
        "like",
        "as",
        "primary",
        "foreign",
        "key",
        "constraint",
        "check",
        "default",
        "values",
        "into",
        "user",
    }

    def normalize_identifier(self, name: str) -> str:
        """Produce a clean, safe normalized SQL identifier from any language."""
        if not name or not name.strip():
            return "unnamed_column"

        # 1. Unicode normalize (NFKC)
        normalized = unicodedata.normalize("NFKC", name.strip())

        # 2. Replace whitespace and punctuation with underscores
        # Allow alphanumeric characters from all languages (Arabic, Turkish, Latin, etc.)
        cleaned = re.sub(r"[^\w]+", "_", normalized, flags=re.UNICODE)

        # 3. Collapse multiple underscores and strip ends
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")

        # 4. Handle leading digits
        if cleaned and cleaned[0].isdigit():
            cleaned = f"col_{cleaned}"

        if not cleaned:
            cleaned = "unnamed_column"

        # 5. Handle SQL reserved words
        lower_cleaned = cleaned.lower()
        if lower_cleaned in self.RESERVED_SQL_WORDS:
            cleaned = f"{cleaned}_col"

        return cleaned

    def normalize_schema(
        self,
        raw_columns: list[str],
        inferred_types: dict[str, ColumnDataType] | None = None,
    ) -> list[ColumnDefinition]:
        """Normalize list of column headers into unique, unambiguous ColumnDefinitions."""
        seen_names: dict[str, int] = {}
        definitions: list[ColumnDefinition] = []
        inferred = inferred_types or {}

        for idx, raw_name in enumerate(raw_columns):
            norm_name = self.normalize_identifier(raw_name)

            # Handle duplicate column names deterministically (case-insensitive for SQL safety)
            key = norm_name.lower()
            if key in seen_names:
                seen_names[key] += 1
                unique_norm_name = f"{norm_name}_{seen_names[key]}"
            else:
                seen_names[key] = 0
                unique_norm_name = norm_name

            col_type = inferred.get(raw_name, ColumnDataType.STRING)

            definitions.append(
                ColumnDefinition(
                    name=raw_name,
                    normalized_name=unique_norm_name,
                    original_name=raw_name,
                    data_type=col_type,
                    nullable=True,
                    ordinal_position=idx + 1,
                )
            )

        return definitions

    def normalize_row(
        self,
        row: dict[str, Any],
        column_mapping: dict[str, str],
    ) -> dict[str, Any]:
        """Transform row dictionary keys from raw column names to normalized names."""
        normalized_row: dict[str, Any] = {}
        for raw_key, value in row.items():
            norm_key = column_mapping.get(raw_key, self.normalize_identifier(raw_key))

            # Normalize string values: strip null bytes and trim whitespace
            if isinstance(value, str):
                cleaned_val = value.replace("\x00", "").strip()
                normalized_row[norm_key] = cleaned_val if cleaned_val != "" else None
            else:
                normalized_row[norm_key] = value

        return normalized_row
