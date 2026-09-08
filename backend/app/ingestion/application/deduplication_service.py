"""Deduplication service supporting row hashing, primary keys, and composite keys."""

import hashlib
import json
from typing import Any

from app.ingestion.domain.enums import DeduplicationStrategy


class DeduplicationService:
    """Filters duplicate rows based on configured deduplication strategies."""

    def compute_row_hash(self, row: dict[str, Any]) -> str:
        """Compute stable deterministic SHA-256 hash of a tabular row."""
        canonical_str = json.dumps(row, sort_keys=True, default=str)
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def deduplicate_rows(
        self,
        rows: list[dict[str, Any]],
        strategy: DeduplicationStrategy = DeduplicationStrategy.EXACT_ROW_HASH,
        keys: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Filter duplicate rows, returning deduplicated rows and duplicate count."""
        if strategy == DeduplicationStrategy.NONE or not rows:
            return rows, 0

        dedup_keys = keys or []
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        duplicate_count = 0

        for row in rows:
            if strategy == DeduplicationStrategy.EXACT_ROW_HASH:
                row_id = self.compute_row_hash(row)
            elif strategy == DeduplicationStrategy.PRIMARY_KEY:
                pk = dedup_keys[0] if dedup_keys else "id"
                row_id = str(row.get(pk, self.compute_row_hash(row)))
            elif strategy == DeduplicationStrategy.COMPOSITE_KEY:
                if dedup_keys:
                    row_id = "|".join(str(row.get(k, "")) for k in dedup_keys)
                else:
                    row_id = self.compute_row_hash(row)

            if row_id in seen:
                duplicate_count += 1
            else:
                seen.add(row_id)
                deduped.append(row)

        return deduped, duplicate_count
