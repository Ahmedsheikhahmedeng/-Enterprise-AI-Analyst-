"""Unit tests for Cross-Encoder providers, batching, and input validators."""

import uuid

import pytest

from app.reranking.batching import create_batches
from app.reranking.config import RerankerConfig
from app.reranking.exceptions import (
    RerankerConfigurationError,
    RerankerInputError,
    RerankerModelLoadError,
    RerankerTenantError,
)
from app.reranking.providers.factory import RerankerProviderFactory
from app.reranking.providers.local import LocalDeterministicCrossEncoderProvider
from app.reranking.providers.sentence_transformers import (
    SentenceTransformersRerankerProvider,
)
from app.reranking.validators import RerankerValidator
from app.retrieval.hybrid.models import FusedCandidate


class TestLocalDeterministicCrossEncoder:
    """Unit test suite for LocalDeterministicCrossEncoderProvider."""

    @pytest.fixture
    def provider(self) -> LocalDeterministicCrossEncoderProvider:
        return LocalDeterministicCrossEncoderProvider()

    @pytest.mark.asyncio
    async def test_score_pairs_length_and_order(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify output length and order strictly match input pairs."""
        pairs = [
            ("What is revenue?", "Revenue was $100M in 2025."),
            ("What is EBITDA?", "EBITDA was $25M in 2025."),
            ("Who is CEO?", "Jane Doe is the CEO of the enterprise."),
        ]
        scores = await provider.score_pairs(pairs)
        assert len(scores) == 3
        assert all(isinstance(s, float) for s in scores)
        assert all(0.0 <= s <= 1.0 for s in scores)

    @pytest.mark.asyncio
    async def test_empty_pairs_returns_empty_list(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify empty input returns empty list without error."""
        scores = await provider.score_pairs([])
        assert scores == []

    @pytest.mark.asyncio
    async def test_relevant_pair_scores_higher_than_irrelevant(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify relevant query-candidate pair gets significantly higher score than irrelevant."""
        query = "What caused the decline in operating margin?"
        relevant_text = (
            "The decline in operating margin was primarily caused by supply chain disruptions "
            "and sharp increases in raw material shipping rates."
        )
        irrelevant_text = (
            "The annual corporate summer picnic will be hosted at Green Valley Lake next Saturday."
        )

        scores = await provider.score_pairs([(query, relevant_text), (query, irrelevant_text)])
        rel_score, irrel_score = scores[0], scores[1]
        assert rel_score > irrel_score
        assert rel_score > 0.6
        assert irrel_score < 0.4

    @pytest.mark.asyncio
    async def test_exact_phrase_and_business_codes(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify exact product ID 'XJ-4927' and quarter 'Q4 2025' receive high relevance."""
        query = "Project XJ-4927 Q4 2025"
        exact_text = (
            "Under Project XJ-4927 Q4 2025 deliverables, the team completed hardware integration."
        )
        partial_text = "Project progress was steady throughout late 2025 across all active units."

        scores = await provider.score_pairs([(query, exact_text), (query, partial_text)])
        assert scores[0] > scores[1]

    @pytest.mark.asyncio
    async def test_multilingual_arabic(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify Arabic question matches Arabic answering document."""
        query = "ما سبب انخفاض هامش التشغيل؟"
        rel_ar = "انخفض هامش التشغيل بسبب ارتفاع تكاليف المواد الخام وشحن البضائع."
        irrel_ar = "تأسست الشركة في عام ألف وتسعمائة وتسعين في مدينة الرياض."

        scores = await provider.score_pairs([(query, rel_ar), (query, irrel_ar)])
        assert scores[0] > scores[1]

    @pytest.mark.asyncio
    async def test_multilingual_turkish(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify Turkish question matches Turkish answering document with dotted/dotless I."""
        query = "Faaliyet marjındaki düşüşün nedeni neydi?"
        rel_tr = (
            "Faaliyet marjı, lojistik harcamalarındaki artış nedeniyle belirgin şekilde daraldı."
        )
        irrel_tr = (
            "Yıllık olağan genel kurul toplantısı İstanbul merkez binasında gerçekleştirildi."
        )

        scores = await provider.score_pairs([(query, rel_tr), (query, irrel_tr)])
        assert scores[0] > scores[1]

    @pytest.mark.asyncio
    async def test_multilingual_mixed_language(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify mixed Arabic, Turkish, English corporate document is processed without error."""
        query = "Operating Margin — هامش التشغيل — Faaliyet Marjı"
        doc = (
            "Financial KPI summary: Operating Margin fell to 12% "
            "(هامش التشغيل: %12, Faaliyet Marjı: %12)."
        )
        scores = await provider.score_pairs([(query, doc)])
        assert len(scores) == 1
        assert scores[0] > 0.5

    @pytest.mark.asyncio
    async def test_deterministic_scoring(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify identical inputs produce strictly identical scores."""
        pair = ("What is the capital expenditure?", "CapEx was $50 million.")
        score1 = (await provider.score_pairs([pair]))[0]
        score2 = (await provider.score_pairs([pair]))[0]
        assert score1 == score2

    def test_provider_metadata_and_health(
        self, provider: LocalDeterministicCrossEncoderProvider
    ) -> None:
        """Verify provider inspection properties."""
        assert provider.provider_name == "local"
        assert provider.device == "cpu"
        assert provider.version == "reranker-v1"


class TestBatchingAndValidators:
    """Unit test suite for batching utilities and validation safety rules."""

    def test_create_batches_partitioning(self) -> None:
        """Verify batching correctly partitions sequences into expected chunk sizes."""
        items = list(range(10))
        batches = create_batches(items, batch_size=4)
        assert len(batches) == 3
        assert batches[0] == [0, 1, 2, 3]
        assert batches[1] == [4, 5, 6, 7]
        assert batches[2] == [8, 9]

    def test_create_batches_empty_and_remainder(self) -> None:
        """Verify batching handles empty input and exact divisions."""
        assert create_batches([], batch_size=5) == []
        assert len(create_batches([1, 2, 3], batch_size=3)) == 1

    def test_create_batches_invalid_size_raises(self) -> None:
        """Verify batch_size < 1 raises RerankerInputError."""
        with pytest.raises(RerankerInputError):
            create_batches([1, 2], batch_size=0)

    def test_validator_empty_query_raises(self) -> None:
        """Verify empty or whitespace query raises RerankerInputError."""
        with pytest.raises(RerankerInputError):
            RerankerValidator.validate_query("   ")

    def test_validator_tenant_boundary_enforcement(self) -> None:
        """Verify cross-tenant candidates raise RerankerTenantError."""
        org_a = uuid.uuid4()
        org_b = uuid.uuid4()

        valid_cands = [
            FusedCandidate(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                organization_id=org_a,
                rrf_score=0.03,
            )
        ]
        # Should pass
        RerankerValidator.validate_tenant_boundary(valid_cands, organization_id=org_a)

        # Should raise on mismatch
        invalid_cands = [
            FusedCandidate(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                organization_id=org_b,
                rrf_score=0.03,
            )
        ]
        with pytest.raises(RerankerTenantError):
            RerankerValidator.validate_tenant_boundary(invalid_cands, organization_id=org_a)

    def test_validator_truncate_text_if_needed(self) -> None:
        """Verify excessively long text is truncated safely to max_tokens limit."""
        long_text = "word " * 1000
        truncated = RerankerValidator.truncate_text_if_needed(
            long_text, max_tokens=100, approx_chars_per_token=4
        )
        assert len(truncated) < len(long_text)
        assert truncated.endswith("...")


class TestProviderFactoryAndNeuralFallback:
    """Unit test suite for provider factory and neural provider handling."""

    def test_factory_creates_local_provider(self) -> None:
        """Verify factory instantiates LocalDeterministicCrossEncoderProvider."""
        config = RerankerConfig(provider="local")
        provider = RerankerProviderFactory.create(config)
        assert isinstance(provider, LocalDeterministicCrossEncoderProvider)

    def test_factory_unsupported_provider_raises(self) -> None:
        """Verify unsupported provider name raises RerankerConfigurationError."""
        config = RerankerConfig(provider="unsupported-provider-xyz")
        with pytest.raises(RerankerConfigurationError):
            RerankerProviderFactory.create(config)

    def test_sentence_transformers_missing_package_raises(self) -> None:
        """Verify instantiating SentenceTransformers without package raises ModelLoadError."""
        # When sentence-transformers is not in environment, raises RerankerModelLoadError
        with pytest.raises(RerankerModelLoadError) as exc_info:
            SentenceTransformersRerankerProvider(model_name="test-model")
        assert "sentence-transformers" in str(exc_info.value).lower()
