"""Okapi BM25 encoder and scoring engine."""

import uuid

from app.retrieval.config import BM25Config
from app.retrieval.sparse.models import AnalyzedText
from app.retrieval.sparse.stats import (
    TenantCorpusStatsManager,
    get_tenant_corpus_stats_manager,
)
from app.vectorstore.models import SparseVector


class BM25Encoder:
    """Encodes text chunks and queries into sparse vectors for Okapi BM25 retrieval.

    Mathematical Basis:
        score(D, Q) = Σ IDF(q) * ( f(q, D) * (k1 + 1) ) /
                      ( f(q, D) + k1 * (1 - b + b * (|D| / avgdl)) )

    Sparse Vector Mapping:
        - Document vector W_doc(t) = ( f(t, D) * (k1 + 1) ) /
                                     ( f(t, D) + k1 * (1 - b + b * (|D| / avgdl)) )
        - Query vector W_query(q) = IDF(q) * f(q, Q)
        - Vector dot product: W_query · W_doc = score(D, Q)
    """

    def __init__(
        self,
        config: BM25Config | None = None,
        stats_manager: TenantCorpusStatsManager | None = None,
    ) -> None:
        self.config = config or BM25Config()
        self.stats_manager = stats_manager or get_tenant_corpus_stats_manager()

    def encode_document(
        self,
        analyzed: AnalyzedText,
        avgdl: float = 1.0,
    ) -> SparseVector:
        """Encode an analyzed document chunk into a BM25 document sparse vector."""
        if not analyzed.term_frequencies or analyzed.doc_len == 0:
            return SparseVector(indices=[], values=[])

        k1 = self.config.k1
        b = self.config.b
        eff_avgdl = max(1.0, avgdl)
        len_norm = 1.0 - b + b * (analyzed.doc_len / eff_avgdl)

        indices: list[int] = []
        values: list[float] = []

        # Sort indices ascending for standard sparse vector format
        for tok_id in sorted(analyzed.term_frequencies.keys()):
            tf = analyzed.term_frequencies[tok_id]
            # TF component with saturation and length normalization
            weight = (tf * (k1 + 1.0)) / (tf + k1 * len_norm)
            indices.append(tok_id)
            values.append(round(weight, 6))

        return SparseVector(indices=indices, values=values)

    def encode_query(
        self,
        analyzed: AnalyzedText,
        organization_id: uuid.UUID,
    ) -> SparseVector:
        """Encode an analyzed query into an IDF-weighted query sparse vector."""
        if not analyzed.term_frequencies:
            return SparseVector(indices=[], values=[])

        indices: list[int] = []
        values: list[float] = []

        for tok_id in sorted(analyzed.term_frequencies.keys()):
            qf = analyzed.term_frequencies[tok_id]
            idf = self.stats_manager.calculate_idf(organization_id, tok_id)
            query_weight = idf * qf
            indices.append(tok_id)
            values.append(round(query_weight, 6))

        return SparseVector(indices=indices, values=values)

    @staticmethod
    def compute_bm25_score(
        query_vector: SparseVector,
        doc_vector: SparseVector,
    ) -> float:
        """Compute exact BM25 dot product between query and document sparse vectors."""
        if not query_vector.indices or not doc_vector.indices:
            return 0.0

        q_dict = dict(zip(query_vector.indices, query_vector.values, strict=False))
        score = sum(
            q_dict[idx] * val
            for idx, val in zip(doc_vector.indices, doc_vector.values, strict=False)
            if idx in q_dict
        )
        return float(score)
