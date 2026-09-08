"""Tenant-scoped corpus statistics manager for BM25 IDF calculations."""

import math
import threading
from uuid import UUID

from app.retrieval.sparse.models import AnalyzedText, TenantCorpusStats


class TenantCorpusStatsManager:
    """Thread-safe multi-tenant corpus statistics registry.

    Guarantees:
    - Complete tenant isolation: organization A's term frequencies and document counts
      never affect organization B's BM25 scoring or IDF calculations.
    - O(1) term document frequency lookup and IDF computation.
    - Thread safety across concurrent indexing and retrieval operations.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stats: dict[UUID, TenantCorpusStats] = {}

    def get_stats(self, organization_id: UUID) -> TenantCorpusStats:
        """Retrieve corpus stats for an organization, initializing defaults if absent."""
        with self._lock:
            if organization_id not in self._stats:
                self._stats[organization_id] = TenantCorpusStats(organization_id=organization_id)
            return self._stats[organization_id]

    def register_chunk(self, organization_id: UUID, analyzed: AnalyzedText) -> None:
        """Update tenant corpus statistics with a newly indexed chunk."""
        with self._lock:
            stats = self.get_stats(organization_id)
            stats.document_count += 1
            stats.total_tokens += analyzed.doc_len

            # Update document frequency for each unique term
            for tok_id in analyzed.term_frequencies:
                stats.document_frequencies[tok_id] = stats.document_frequencies.get(tok_id, 0) + 1

    def register_chunks_batch(
        self,
        organization_id: UUID,
        analyzed_chunks: list[AnalyzedText],
    ) -> None:
        """Batch update tenant corpus statistics."""
        with self._lock:
            stats = self.get_stats(organization_id)
            for analyzed in analyzed_chunks:
                stats.document_count += 1
                stats.total_tokens += analyzed.doc_len
                for tok_id in analyzed.term_frequencies:
                    stats.document_frequencies[tok_id] = (
                        stats.document_frequencies.get(tok_id, 0) + 1
                    )

    def unregister_chunk(self, organization_id: UUID, analyzed: AnalyzedText) -> None:
        """Remove a chunk from tenant corpus statistics upon deletion."""
        with self._lock:
            if organization_id not in self._stats:
                return
            stats = self._stats[organization_id]
            stats.document_count = max(0, stats.document_count - 1)
            stats.total_tokens = max(0, stats.total_tokens - analyzed.doc_len)
            for tok_id in analyzed.term_frequencies:
                current_df = stats.document_frequencies.get(tok_id, 0)
                if current_df <= 1:
                    stats.document_frequencies.pop(tok_id, None)
                else:
                    stats.document_frequencies[tok_id] = current_df - 1

    def calculate_idf(self, organization_id: UUID, token_id: int) -> float:
        """Compute Robertson-Spärck Jones smoothed IDF for a token within tenant scope.

        Formula:
            IDF(q) = ln(1 + (N - n(q) + 0.5) / (n(q) + 0.5))

        Guarantees strictly positive IDF values even when a term appears in all documents.
        """
        stats = self.get_stats(organization_id)
        n_total = stats.document_count
        df = stats.document_frequencies.get(token_id, 0)

        if n_total <= 0:
            # Cold start / unindexed tenant default
            return 1.0

        # Lucene / Robertson-Spärck Jones smoothed BM25 IDF
        idf = math.log(1.0 + (n_total - df + 0.5) / (df + 0.5))
        return max(0.01, idf)

    def reset_tenant(self, organization_id: UUID) -> None:
        """Reset corpus statistics for a specific tenant."""
        with self._lock:
            self._stats.pop(organization_id, None)

    def clear(self) -> None:
        """Clear all corpus statistics across all tenants."""
        with self._lock:
            self._stats.clear()


# Global default singleton instance
_global_stats_manager = TenantCorpusStatsManager()


def get_tenant_corpus_stats_manager() -> TenantCorpusStatsManager:
    """Return singleton instance of TenantCorpusStatsManager."""
    return _global_stats_manager
