"""Intent classification and route selection across SQL, RAG, and HYBRID modalities."""

import re
from dataclasses import dataclass
from uuid import UUID

from app.analyst.models import AnalystRouteType


@dataclass(frozen=True)
class RouteClassificationResult:
    """Semantic route decision and confidence scoring."""

    route: AnalystRouteType
    confidence: float
    has_structured_intent: bool
    has_unstructured_intent: bool
    structured_subquery: str | None = None
    unstructured_subquery: str | None = None
    reason: str = ""


class AnalystQueryRouter:
    """Classifies user queries into SQL, RAG, or HYBRID execution routes."""

    # Structured / Numerical cues
    STRUCTURED_KEYWORDS = {
        # English
        "revenue",
        "sales",
        "profit",
        "margin",
        "growth",
        "total",
        "sum",
        "average",
        "avg",
        "count",
        "quarter",
        "q1",
        "q2",
        "q3",
        "q4",
        "how much",
        "how many",
        "metrics",
        "dataset",
        "table",
        "numbers",
        "breakdown",
        "decline",
        "increase",
        # Arabic
        "إيراد",
        "إيرادات",
        "مبيعات",
        "أرباح",
        "ربح",
        "مجموع",
        "متوسط",
        "نسبة",
        "نمو",
        "ربع سنوي",
        "الربع",
        "كم",
        "إجمالي",
        "جدول",
        "انخفاض",
        "ارتفاع",
        # Turkish
        "gelir",
        "satış",
        "kâr",
        "büyüme",
        "toplam",
        "ortalama",
        "çeyrek",
        "ne kadar",
        "sayı",
        "tablo",
        "düşüş",
        "artış",
    }

    # Unstructured / Document cues
    UNSTRUCTURED_KEYWORDS = {
        # English
        "report",
        "annual report",
        "filing",
        "document",
        "policy",
        "mention",
        "say",
        "state",
        "according to",
        "why",
        "reason",
        "explanation",
        "attribute",
        "cause",
        "strategy",
        "discuss",
        "summary",
        "clause",
        "contract",
        # Arabic
        "تقرير",
        "التقرير السنوي",
        "وثيقة",
        "مستند",
        "سياسة",
        "ذكر",
        "يقول",
        "لماذا",
        "سبب",
        "تفسير",
        "عزى",
        "استراتيجية",
        "عقد",
        "بند",
        # Turkish
        "rapor",
        "yıllık rapor",
        "belge",
        "doküman",
        "politika",
        "söylüyor",
        "bahsediyor",
        "neden",
        "sebep",
        "açıklama",
        "strateji",
        "sözleşme",
    }

    def classify(
        self,
        query: str,
        datasource_id: UUID | None = None,
    ) -> RouteClassificationResult:
        """Classify incoming natural language query into an AnalystRouteType."""
        q_lower = query.lower()

        # Keyword matching: ASCII short words use boundary matching; non-ASCII/Arabic use substring
        def _contains_kw(kw: str, text: str) -> bool:
            if kw.isascii() and len(kw) <= 4:
                return bool(re.search(rf"\b{re.escape(kw)}\b", text))
            return kw in text

        has_struct_words = any(_contains_kw(kw, q_lower) for kw in self.STRUCTURED_KEYWORDS)
        has_unstruct_words = any(_contains_kw(kw, q_lower) for kw in self.UNSTRUCTURED_KEYWORDS)

        # Check for explicit multi-part questions (e.g. "and what does the report say")
        has_conjunction = any(
            conj in q_lower
            for conj in [
                " and ",
                " & ",
                " but ",
                " while ",
                " also ",
                " و",
                " ولكن ",
                " بينما ",
                " مع ",
                " ve ",
                " fakat ",
                " ile birlikte ",
            ]
        )

        # Case 1: HYBRID
        # Query has both structured & unstructured signals AND datasource_id is available
        if datasource_id is not None and (
            (has_struct_words and has_unstruct_words) or (has_conjunction and has_struct_words)
        ):
            return RouteClassificationResult(
                route=AnalystRouteType.HYBRID,
                confidence=0.92,
                has_structured_intent=True,
                has_unstructured_intent=True,
                structured_subquery=query,
                unstructured_subquery=query,
                reason="Query combines quantitative metrics with qualitative document explanation.",
            )

        # Case 2: SQL (Structured)
        if has_struct_words and datasource_id is not None:
            return RouteClassificationResult(
                route=AnalystRouteType.SQL,
                confidence=0.95,
                has_structured_intent=True,
                has_unstructured_intent=False,
                structured_subquery=query,
                reason="Query is primarily focused on structured quantitative calculations.",
            )

        # Case 3: RAG (Unstructured)
        if has_unstruct_words or datasource_id is None:
            return RouteClassificationResult(
                route=AnalystRouteType.RAG,
                confidence=0.90 if has_unstruct_words else 0.75,
                has_structured_intent=False,
                has_unstructured_intent=True,
                unstructured_subquery=query,
                reason="Query is focused on document retrieval and contextual synthesis.",
            )

        # Default fallback to RAG as the safest document route
        return RouteClassificationResult(
            route=AnalystRouteType.RAG,
            confidence=0.70,
            has_structured_intent=False,
            has_unstructured_intent=True,
            unstructured_subquery=query,
            reason="Defaulting to document retrieval as safest route.",
        )
