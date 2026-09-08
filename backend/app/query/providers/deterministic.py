"""Deterministic rule-based query understanding provider."""

from app.query.decomposition import QueryDecomposer
from app.query.entities import EntityExtractor
from app.query.expansion import QueryExpander
from app.query.intent import IntentClassifier
from app.query.language import LanguageDetector
from app.query.models import QueryAnalysis
from app.query.normalization import QueryNormalizer
from app.query.rewrite import QueryRewriter


class DeterministicQueryUnderstandingProvider:
    """100% offline deterministic provider utilizing lexical patterns and regex rules."""

    provider_name = "deterministic_rules"
    model_name = "rules-multilingual-v1"
    version = "1.0.0"

    def __init__(self) -> None:
        self.normalizer = QueryNormalizer()
        self.language_detector = LanguageDetector()
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.rewriter = QueryRewriter()
        self.expander = QueryExpander()
        self.decomposer = QueryDecomposer()

    async def analyze(
        self,
        query: str,
        *,
        enable_rewrite: bool = True,
        enable_expansion: bool = True,
        enable_decomposition: bool = True,
        max_alternatives: int = 3,
        max_subqueries: int = 3,
    ) -> QueryAnalysis:
        """Execute full deterministic query understanding pipeline."""
        # 1. Normalize
        normalized = self.normalizer.normalize(query)

        # 2. Language Detection
        lang_res = self.language_detector.detect(normalized)

        # 3. Intent Classification
        intent, intent_conf = self.intent_classifier.classify(normalized)

        # 4. Entity Extraction
        entities = self.entity_extractor.extract(normalized)

        # 5. Query Rewrite
        rewritten: str | None = None
        if enable_rewrite:
            rewritten = self.rewriter.rewrite(normalized, intent)

        # 6. Query Expansion
        expanded: list[str] = []
        if enable_expansion:
            base_for_expansion = rewritten or normalized
            expanded = self.expander.expand(
                base_for_expansion,
                language=lang_res.primary_language,
                max_expansions=max_alternatives,
            )

        # 7. Query Decomposition
        subqueries: list[str] = []
        if enable_decomposition:
            subqueries = self.decomposer.decompose(
                normalized, intent=intent, max_subqueries=max_subqueries
            )

        # Overall confidence
        confidence = round(float(lang_res.confidence * intent_conf), 4)

        return QueryAnalysis(
            original_query=query,
            normalized_query=normalized,
            language=lang_res.primary_language,
            detected_languages=lang_res.detected_languages,
            intent=intent,
            entities=entities,
            rewritten_query=rewritten,
            expanded_queries=expanded,
            sub_queries=subqueries,
            confidence=confidence,
        )

    async def health_check(self) -> bool:
        return True
