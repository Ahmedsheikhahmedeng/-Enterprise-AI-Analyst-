"""Unit tests for MultilingualSparseAnalyzer and token hashing."""

from app.retrieval.config import BM25Config
from app.retrieval.sparse.analyzer import (
    MultilingualSparseAnalyzer,
    compute_token_id,
    normalize_arabic,
    turkish_lower,
)


class TestTurkishCasing:
    """Tests for Turkish linguistic casing and character preservation."""

    def test_turkish_dotted_and_dotless_i(self) -> None:
        """Verify capital dotted İ becomes small i, capital I becomes small dotless ı."""
        assert turkish_lower("İSTANBUL") == "istanbul"
        assert turkish_lower("ISPARTA") == "ısparta"
        assert turkish_lower("İlgi") == "ilgi"
        assert turkish_lower("Ilık") == "ılık"

    def test_turkish_special_characters_preserved(self) -> None:
        """Verify Turkish letters ş, ğ, ç, ö, ü are preserved and lowercased."""
        input_text = "ŞEKER AĞAÇ ÇİÇEK ÖRDEK ÜZÜM"
        expected = "şeker ağaç çiçek ördek üzüm"
        assert turkish_lower(input_text) == expected


class TestArabicNormalization:
    """Tests for Arabic letter normalization and diacritic handling."""

    def test_arabic_diacritic_stripping(self) -> None:
        """Verify Tashkeel diacritics are removed so vowels don't break matching."""
        vocalized = "أَرْبَاحُ الشَّرِكَةِ"
        unvocalized = "أرباح الشركة"
        analyzer = MultilingualSparseAnalyzer(BM25Config(strip_arabic_diacritics=True))
        assert analyzer.tokenize(vocalized) == analyzer.tokenize(unvocalized)

    def test_arabic_letter_shapes_standardized(self) -> None:
        """Verify Hamza variants, Taa Marbuta, and Alef Maksura are normalized."""
        text = "إدارة الأصول والمصارف الإسلامية في مصر والقرى"
        normalized = normalize_arabic(text)
        assert "اداره" in normalized  # ة -> ه
        assert "الاصول" in normalized  # أ -> ا
        assert "الاسلاميه" in normalized  # إ -> ا, ة -> ه
        assert "القري" in normalized  # ى -> ي

    def test_arabic_indic_digits_converted(self) -> None:
        """Verify Eastern Arabic digits (٠-٩) are normalized to Western (0-9)."""
        text = "تقرير عام ٢٠٢٥ للربع ٤"
        normalized = normalize_arabic(text)
        assert "2025" in normalized
        assert "4" in normalized


class TestEnglishAndBusinessTokens:
    def test_business_identifiers_and_numbers_preserved(self) -> None:
        """Verify codes like Q4, 2025, 15%, and XJ-4927 are not stripped or mangled."""
        analyzer = MultilingualSparseAnalyzer()
        text = "Q4 2025 Revenue grew by 15% under Project XJ-4927 (SKU: PROD-998)"
        tokens = analyzer.tokenize(text)
        assert "q4" in tokens
        assert "2025" in tokens
        assert "15%" in tokens
        assert "xj-4927" in tokens
        assert "prod-998" in tokens

    def test_currency_and_version_tokens(self) -> None:
        """Verify EUR-500, USD, and version tags v1.2."""
        analyzer = MultilingualSparseAnalyzer()
        tokens = analyzer.tokenize("Payment of EUR-500 for firmware v2.4.")
        assert "eur-500" in tokens
        assert "v2.4" in tokens


class TestMixedLanguage:
    """Tests for complex mixed-language strings."""

    def test_mixed_language_sentence(self) -> None:
        """Verify query with English, Arabic, and Turkish."""
        text = "2025 Revenue Analysis — تحليل الإيرادات — Gelir Analizi (Q4, 15%, XJ-4927)"
        analyzer = MultilingualSparseAnalyzer()
        res = analyzer.analyze(text)

        expected_tokens = [
            "2025",
            "revenue",
            "analysis",
            "تحليل",
            "الايرادات",
            "gelir",
            "analizi",
            "q4",
            "15%",
            "xj-4927",
        ]
        for exp in expected_tokens:
            assert exp in res.tokens
        assert res.doc_len == len(res.tokens)

    def test_empty_and_whitespace_input(self) -> None:
        """Verify empty and whitespace queries return empty token lists safely."""
        analyzer = MultilingualSparseAnalyzer()
        assert analyzer.tokenize("") == []
        assert analyzer.tokenize("   \n\t  ") == []
        assert analyzer.analyze("").term_frequencies == {}


class TestDeterministicTokenHashing:
    """Tests for deterministic integer token hashing and versioning."""

    def test_hashing_is_deterministic(self) -> None:
        """Same token must produce identical integer ID across calls."""
        id1 = compute_token_id("revenue", "bm25-v1")
        id2 = compute_token_id("revenue", "bm25-v1")
        assert id1 == id2
        assert isinstance(id1, int)
        assert id1 > 0

    def test_versioning_isolates_token_ids(self) -> None:
        """Different version tag must produce different integer ID for the same token."""
        id_v1 = compute_token_id("revenue", "bm25-v1")
        id_v2 = compute_token_id("revenue", "bm25-v2")
        assert id_v1 != id_v2

    def test_multilingual_tokens_hash_safely(self) -> None:
        """Tokens in Arabic, Turkish, and English produce valid non-zero positive IDs."""
        tokens = ["revenue", "ارباح", "şeker", "xj-4927", "2025"]
        for t in tokens:
            tid = compute_token_id(t, "bm25-v1")
            assert 0 < tid <= 0x7FFFFFFF
