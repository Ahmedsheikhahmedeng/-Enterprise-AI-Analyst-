"""SQL query normalization, SHA-256 hashing, and provenance audit tracking."""

import hashlib
import re
from uuid import UUID

from app.sql_agent.models import SQLProvenance


class SQLProvenanceTracker:
    """Computes deterministic hashes and execution provenance records for auditability."""

    @staticmethod
    def normalize_sql(raw_sql: str) -> str:
        """Deterministic SQL normalization: standardizes whitespace, punctuation, and casing."""
        # Collapse multi-line whitespaces into single space
        normalized = re.sub(r"\s+", " ", raw_sql.strip())
        # Standardize semicolons at end
        normalized = normalized.rstrip(";").strip() + ";"
        return normalized

    @classmethod
    def compute_sql_hash(cls, sql: str) -> str:
        """Compute SHA-256 digest over normalized SQL."""
        norm = cls.normalize_sql(sql)
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()

    @classmethod
    def create_provenance(
        cls,
        sql: str,
        datasource_id: UUID,
        tables_used: list[str],
        columns_used: list[str],
        row_count: int,
        duration_ms: float,
    ) -> SQLProvenance:
        """Construct immutable SQLProvenance metadata object."""
        normalized = cls.normalize_sql(sql)
        sql_hash = cls.compute_sql_hash(normalized)

        return SQLProvenance(
            sql_hash=sql_hash,
            datasource_id=str(datasource_id),
            tables_used=sorted(set(tables_used)),
            columns_used=sorted(set(columns_used)),
            row_count=row_count,
            duration_ms=duration_ms,
            normalized_sql=normalized,
        )
