"""Unit tests for BM25 encoding, scoring, and multi-tenant corpus statistics."""

import uuid

from app.retrieval.config import BM25Config
from app.retrieval.sparse.analyzer import MultilingualSparseAnalyzer
from app.retrieval.sparse.bm25 import BM25Encoder
from app.retrieval.sparse.stats import TenantCorpusStatsManager


class TestTenantCorpusStatsManager:
    """Tests for multi-tenant isolation and aggregation of corpus statistics."""

    def test_tenant_isolation_in_statistics(self) -> None:
        """Verify organization A documents never affect organization B statistics."""
        manager = TenantCorpusStatsManager()
        analyzer = MultilingualSparseAnalyzer()

        org_a = uuid.uuid4()
        org_b = uuid.uuid4()

        doc_a1 = analyzer.analyze("financial report revenue Q4 2025")
        doc_a2 = analyzer.analyze("quarterly revenue report")
        manager.register_chunk(org_a, doc_a1)
        manager.register_chunk(org_a, doc_a2)

        doc_b1 = analyzer.analyze("medical healthcare clinical research")
        manager.register_chunk(org_b, doc_b1)

        stats_a = manager.get_stats(org_a)
        stats_b = manager.get_stats(org_b)

        assert stats_a.document_count == 2
        assert stats_b.document_count == 1

        rev_token_id = list(analyzer.analyze("revenue").term_frequencies.keys())[0]

        # Token 'revenue' appears in Org A twice, Org B 0 times
        assert stats_a.document_frequencies.get(rev_token_id) == 2
        assert stats_b.document_frequencies.get(rev_token_id, 0) == 0

        # IDF of 'revenue' in Org A is lower than Org B (since Org B never saw it)
        idf_a = manager.calculate_idf(org_a, rev_token_id)
        idf_b = manager.calculate_idf(org_b, rev_token_id)
        assert idf_a < idf_b

    def test_unregister_chunk_updates_counts(self) -> None:
        """Verify unregistering a chunk decrements document count and token frequency."""
        manager = TenantCorpusStatsManager()
        analyzer = MultilingualSparseAnalyzer()
        org_id = uuid.uuid4()

        doc = analyzer.analyze("alpha beta gamma")
        manager.register_chunk(org_id, doc)

        stats = manager.get_stats(org_id)
        assert stats.document_count == 1
        assert stats.total_tokens == 3

        manager.unregister_chunk(org_id, doc)
        assert stats.document_count == 0
        assert stats.total_tokens == 0


class TestBM25EncoderAndScoring:
    """Tests for Okapi BM25 sparse vector encoding and dot product scoring."""

    def test_document_sparse_vector_encoding(self) -> None:
        """Verify TF saturation and length normalization in document vector."""
        analyzer = MultilingualSparseAnalyzer()
        encoder = BM25Encoder(BM25Config(k1=1.2, b=0.75))

        # Doc with term 'revenue' repeated 3 times
        doc = analyzer.analyze("revenue revenue revenue growth")
        sparse_vec = encoder.encode_document(doc, avgdl=4.0)

        assert len(sparse_vec.indices) == 2  # 'revenue' and 'growth'
        # Indices are sorted ascending
        assert sparse_vec.indices == sorted(sparse_vec.indices)

        # Revenue weight > growth weight (higher term frequency)
        rev_id = list(analyzer.analyze("revenue").term_frequencies.keys())[0]
        growth_id = list(analyzer.analyze("growth").term_frequencies.keys())[0]

        idx_rev = sparse_vec.indices.index(rev_id)
        idx_growth = sparse_vec.indices.index(growth_id)

        assert sparse_vec.values[idx_rev] > sparse_vec.values[idx_growth]

    def test_empty_document_produces_empty_vector(self) -> None:
        """Verify empty document produces empty indices and values."""
        analyzer = MultilingualSparseAnalyzer()
        encoder = BM25Encoder()
        empty_doc = analyzer.analyze("")
        vec = encoder.encode_document(empty_doc)
        assert vec.indices == []
        assert vec.values == []

    def test_exact_bm25_dot_product_scoring(self) -> None:
        """Verify exact BM25 dot product between query and document vectors."""
        analyzer = MultilingualSparseAnalyzer()
        stats_mgr = TenantCorpusStatsManager()
        encoder = BM25Encoder(stats_manager=stats_mgr)

        org_id = uuid.uuid4()
        # Register 10 docs to create non-trivial IDF
        for i in range(10):
            stats_mgr.register_chunk(org_id, analyzer.analyze(f"general report {i}"))

        # Doc 1 contains exact keyword "XJ-4927"
        doc1 = analyzer.analyze("Project status for module XJ-4927 completed")
        stats_mgr.register_chunk(org_id, doc1)

        # Doc 2 does NOT contain keyword
        doc2 = analyzer.analyze("Project status for module ABC-1111 completed")
        stats_mgr.register_chunk(org_id, doc2)

        q = analyzer.analyze("XJ-4927")
        q_vec = encoder.encode_query(q, org_id)

        doc1_vec = encoder.encode_document(doc1, avgdl=stats_mgr.get_stats(org_id).avgdl)
        doc2_vec = encoder.encode_document(doc2, avgdl=stats_mgr.get_stats(org_id).avgdl)

        score1 = BM25Encoder.compute_bm25_score(q_vec, doc1_vec)
        score2 = BM25Encoder.compute_bm25_score(q_vec, doc2_vec)

        assert score1 > 0.0
        assert score2 == 0.0
