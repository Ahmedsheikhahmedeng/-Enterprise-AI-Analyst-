"""Standardized provenance and citation formatting across SQL and RAG sources."""

from typing import Any

from app.analyst.models import UnifiedEvidence
from app.analyst.schemas import CitationItem


class AnalystProvenanceTracker:
    """Constructs clean, sanitized citation items from UnifiedEvidence."""

    @staticmethod
    def build_citations(
        evidence: list[UnifiedEvidence],
        cited_ids: set[str] | list[str] | None = None,
    ) -> list[CitationItem]:
        """Generate client-safe citation items filtered by cited IDs if provided."""
        citations: list[CitationItem] = []
        filter_set = set(cited_ids) if cited_ids is not None else None

        for ev in evidence:
            if filter_set is not None and ev.evidence_id not in filter_set:
                continue

            # Strip any internal connection secrets from metadata
            safe_meta: dict[str, Any] = {}
            for k, v in ev.metadata.items():
                if k in ("password", "connection_string", "user", "secret"):
                    continue
                safe_meta[k] = v

            citations.append(
                CitationItem(
                    id=ev.evidence_id,
                    type=ev.source_type,
                    title=ev.title,
                    is_calculated=ev.is_calculated,
                    metadata=safe_meta,
                )
            )

        return citations
