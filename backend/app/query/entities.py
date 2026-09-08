"""Entity extraction and structured filter classification."""

import re
from typing import Any

from app.query.models import ExtractedEntity


class EntityExtractor:
    """Extracts domain entities and separates explicit facts from soft relevance hints."""

    # Regex patterns for enterprise entities
    _YEAR_RE = re.compile(r"\b(19\d\d|20\d\d)\b")
    _QUARTER_RE = re.compile(r"\b([qQ][1-4]|Q[1-4]|الربع\s+[1-4]|çeyrek\s+[1-4])\b", re.I)
    _PERCENT_RE = re.compile(r"(?:\b|^)(\d+(?:\.\d+)?\s*%)")
    _CURRENCY_RE = re.compile(
        r"(?:[\$\€\£]\s*\d+(?:\.\d+)?(?:\s*(?:million|billion|M|B|k|K))?|\d+(?:\.\d+)?\s*(?:USD|EUR|TRY|SAR|AED|dollar|dollars|TL|lira))",
        re.I,
    )
    _PRODUCT_CODE_RE = re.compile(r"\b([A-Z]{2,5}-\d{2,6})\b")

    # Known domain metrics
    _METRIC_KEYWORDS = {
        "revenue": ["revenue", "إيرادات", "الإيرادات", "gelir", "gelirler", "turnover", "sales"],
        "operating_margin": [
            "operating margin",
            "operating profitability",
            "هامش التشغيل",
            "faaliyet marjı",
            "faaliyet marji",
            "operating profit",
        ],
        "net_income": [
            "net income",
            "net profit",
            "صافي الدخل",
            "صافي الربح",
            "net kâr",
            "net kar",
        ],
        "ebitda": ["ebitda", "الربح قبل الفوائد والضرائب", "favök", "favok"],
        "cash_flow": ["cash flow", "free cash flow", "التدفق النقدي", "nakit akışı", "nakit akisi"],
    }

    # Common corporate identifiers (capitalized tokens or known names)
    _COMPANY_RE = re.compile(
        r"\b([A-Z][A-Za-z0-9]+(?:\s+(?:Corp|Inc|Ltd|LLC|Holding|Group|Company|Technologies))?)\b"
    )

    def extract(self, query: str) -> list[ExtractedEntity]:
        """Extract explicit domain entities present in the query."""
        if not query or not query.strip():
            return []

        entities: list[ExtractedEntity] = []
        seen_keys: set[tuple[str, str]] = set()

        def add_entity(
            name: str, category: str, value: Any, is_explicit: bool = True, conf: float = 1.0
        ) -> None:
            key = (category, str(value).lower())
            if key not in seen_keys:
                seen_keys.add(key)
                entities.append(
                    ExtractedEntity(
                        name=name,
                        category=category,
                        value=value,
                        is_explicit=is_explicit,
                        confidence=conf,
                    )
                )

        # 1. Product / Project Codes (e.g. XJ-4927)
        for m in self._PRODUCT_CODE_RE.finditer(query):
            add_entity(name="product_code", category="code", value=m.group(1), is_explicit=True)

        # 2. Quarters (e.g. Q4, Q1 2025)
        for m in self._QUARTER_RE.finditer(query):
            q_val = m.group(1).upper()
            if "الربع" in q_val:
                num = re.search(r"\d", q_val)
                q_val = f"Q{num.group(0)}" if num else q_val
            add_entity(name="quarter", category="quarter", value=q_val, is_explicit=True)

        # 3. Years (e.g. 2024, 2025)
        for m in self._YEAR_RE.finditer(query):
            add_entity(name="year", category="year", value=int(m.group(1)), is_explicit=True)

        # 4. Percentages (e.g. 15%)
        for m in self._PERCENT_RE.finditer(query):
            add_entity(name="percentage", category="percentage", value=m.group(1), is_explicit=True)

        # 5. Currencies ($120M, 50 USD)
        for m in self._CURRENCY_RE.finditer(query):
            add_entity(name="currency", category="currency", value=m.group(0), is_explicit=True)

        # 6. Financial Metrics
        query_lower = query.lower()
        for metric_name, aliases in self._METRIC_KEYWORDS.items():
            for alias in aliases:
                if alias in query_lower:
                    add_entity(name=metric_name, category="metric", value=alias, is_explicit=True)
                    break

        # 7. Organization / Company names
        # Check capitalized words that are not common query words
        common_words = {
            "what",
            "why",
            "how",
            "when",
            "where",
            "compare",
            "summarize",
            "operating",
            "fiscal",
        }
        for m in self._COMPANY_RE.finditer(query):
            comp = m.group(1)
            if (
                comp.lower() not in common_words
                and len(comp) > 2
                and comp.lower() not in ("ebitda", "usd", "eur", "try")
                and not self._PRODUCT_CODE_RE.match(comp)
            ):
                add_entity(
                    name="company", category="company", value=comp, is_explicit=True, conf=0.85
                )

        return entities

    def build_filters(
        self, entities: list[ExtractedEntity]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Separate entities into hard filter constraints and soft relevance hints."""
        hard_filters: dict[str, Any] = {}
        soft_filters: dict[str, Any] = {}

        for ent in entities:
            # Explicit years and document codes can form hard criteria if verified
            if ent.category == "code" and ent.is_explicit:
                hard_filters["code"] = ent.value
            elif ent.category == "metric":
                soft_filters["metric"] = ent.value
            elif ent.category == "company":
                soft_filters["company"] = ent.value
            elif ent.category in ("year", "quarter"):
                soft_filters[ent.category] = ent.value

        return hard_filters, soft_filters
