"""Conflict detection service detecting contradictions between structured calculations and text claims."""

import logging
import re
import uuid

from app.response_orchestration.domain.enums import EvidenceSourceType, EvidenceTrustLevel
from app.response_orchestration.domain.models import (
    EvidenceBundle,
    EvidenceConflict,
    EvidenceItem,
)
from app.response_orchestration.domain.protocols import ConflictDetectorProtocol

logger = logging.getLogger(__name__)


class ConflictService(ConflictDetectorProtocol):
    """Identifies factual and numerical contradictions across heterogeneous evidence."""

    _NUMERIC_PATTERN = re.compile(
        r"(\$?\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\s*(?:M|B|K|million|billion|thousand|%)?\b|\$?\b\d+(?:\.\d+)?\s*(?:M|B|K|million|billion|thousand|%)?\b)",
        re.IGNORECASE,
    )

    def _parse_number(self, text: str) -> float | None:
        """Normalize numeric token string to float value."""
        clean = text.replace("$", "").replace(",", "").strip()
        multiplier = 1.0
        if clean.endswith("%"):
            clean = clean[:-1].strip()
        elif clean.lower().endswith("m") or clean.lower().endswith("million"):
            multiplier = 1_000_000.0
            clean = re.sub(r"(?i)m(?:illion)?", "", clean).strip()
        elif clean.lower().endswith("b") or clean.lower().endswith("billion"):
            multiplier = 1_000_000_000.0
            clean = re.sub(r"(?i)b(?:illion)?", "", clean).strip()
        elif clean.lower().endswith("k") or clean.lower().endswith("thousand"):
            multiplier = 1_000.0
            clean = re.sub(r"(?i)k(?:housand)?", "", clean).strip()

        try:
            return float(clean) * multiplier
        except (ValueError, TypeError):
            return None

    def detect_conflicts(self, evidence_bundle: EvidenceBundle) -> list[EvidenceConflict]:
        """Compare numbers and facts across SQL, Semantic, and Document evidence."""
        conflicts: list[EvidenceConflict] = []
        sql_items = evidence_bundle.get_by_source_type(EvidenceSourceType.SQL)
        doc_items = evidence_bundle.get_by_source_type(EvidenceSourceType.DOCUMENT)

        if not sql_items or not doc_items:
            return conflicts

        # 1. Extract numeric values from SQL items
        sql_numbers: list[tuple[EvidenceItem, float, str]] = []
        for it in sql_items:
            metrics = it.metadata.get("metrics", {})
            for m_key, m_val in metrics.items():
                if isinstance(m_val, (int, float)):
                    sql_numbers.append((it, float(m_val), str(m_key)))

            for token in self._NUMERIC_PATTERN.findall(it.content):
                num = self._parse_number(token)
                if num is not None and num > 0:
                    sql_numbers.append((it, num, token))

        # 2. Extract numeric values from document items
        doc_numbers: list[tuple[EvidenceItem, float, str]] = []
        for it in doc_items:
            for token in self._NUMERIC_PATTERN.findall(it.content):
                num = self._parse_number(token)
                if num is not None and num > 0:
                    doc_numbers.append((it, num, token))

        # 3. Pairwise comparison
        seen_keys = set()
        for sql_ev, sql_val, sql_desc in sql_numbers:
            for doc_ev, doc_val, _doc_desc in doc_numbers:
                if sql_val > 0 and doc_val > 0:
                    ratio = abs(sql_val - doc_val) / max(sql_val, doc_val)
                    if 0.05 < ratio < 0.95:
                        dedup_key = (round(sql_val, 2), round(doc_val, 2))
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)

                        conf = EvidenceConflict(
                            conflict_id=str(uuid.uuid4()),
                            field=sql_desc,
                            source_a=f"SQL [{sql_ev.citation_id or 'S'}]",
                            value_a=f"{sql_val:,.2f}",
                            source_b=f"Document [{doc_ev.citation_id or 'D'}]",
                            value_b=f"{doc_val:,.2f}",
                            severity="high" if ratio > 0.20 else "medium",
                            description=(
                                f"Numerical mismatch on '{sql_desc}': SQL reported {sql_val:,.2f} "
                                f"while document sources assert {doc_val:,.2f} (diff {ratio:.1%})."
                            ),
                            resolved_value=f"{sql_val:,.2f}",
                            resolution_reason="Authoritative structured SQL calculations take precedence over unstructured text.",
                        )
                        conflicts.append(conf)
                        doc_ev.trust_level = EvidenceTrustLevel.CONFLICTING

        return conflicts
