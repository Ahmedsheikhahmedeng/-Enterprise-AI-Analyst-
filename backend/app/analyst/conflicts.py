"""Detects factual and numerical contradictions between structured and unstructured sources."""

import re

from app.analyst.models import DataConflict, UnifiedEvidence


class ConflictDetector:
    """Detects discrepancies between SQL calculated values and document assertions."""

    _NUMERIC_PATTERN = re.compile(
        r"(\$?\b\d+(?:[\.,]\d+)?\s*(?:M|B|K|million|billion|thousand|%)?\b)", re.IGNORECASE
    )

    def detect(self, evidence: list[UnifiedEvidence]) -> list[DataConflict]:
        """Inspect evidence items and identify numerical or factual contradictions."""
        conflicts: list[DataConflict] = []

        sql_items = [ev for ev in evidence if ev.source_type == "sql" and ev.is_calculated]
        doc_items = [ev for ev in evidence if ev.source_type == "document"]

        if not sql_items or not doc_items:
            return conflicts

        # Extract numeric values from SQL items
        sql_numbers: list[tuple[UnifiedEvidence, float, str]] = []
        for ev in sql_items:
            # Check metrics
            metrics = ev.metadata.get("metrics", {})
            for m_key, m_val in metrics.items():
                if isinstance(m_val, (int, float)):
                    sql_numbers.append((ev, float(m_val), m_key))
                elif isinstance(m_val, dict):
                    for sub_k, sub_v in m_val.items():
                        try:
                            val_f = float(str(sub_v).replace("$", "").replace(",", ""))
                            sql_numbers.append((ev, val_f, f"{m_key}.{sub_k}"))
                        except (ValueError, TypeError):
                            pass

            # Also check text
            for raw_num in self._NUMERIC_PATTERN.findall(ev.text):
                parsed = self._parse_number(raw_num)
                if parsed is not None:
                    sql_numbers.append((ev, parsed, raw_num))

        # Extract numeric values from document items
        doc_numbers: list[tuple[UnifiedEvidence, float, str]] = []
        for ev in doc_items:
            for raw_num in self._NUMERIC_PATTERN.findall(ev.text):
                parsed = self._parse_number(raw_num)
                if parsed is not None:
                    doc_numbers.append((ev, parsed, raw_num))

        # Compare numbers if both mention revenue/growth or similar orders of magnitude
        for sql_ev, sql_val, sql_desc in sql_numbers:
            for doc_ev, doc_val, _doc_desc in doc_numbers:
                # Discrepancy if values differ by more than 5% and are comparable in scale
                if sql_val > 0 and doc_val > 0:
                    diff_ratio = abs(sql_val - doc_val) / max(sql_val, doc_val)
                    # If within same order of magnitude but divergent by >= 5% and <= 80%
                    if 0.05 <= diff_ratio <= 0.8:
                        conflict_field = sql_desc if isinstance(sql_desc, str) else "metric_value"
                        conflicts.append(
                            DataConflict(
                                field=conflict_field,
                                source_a=f"[{sql_ev.evidence_id}] {sql_ev.title}",
                                value_a=f"{sql_val:,.2f}",
                                source_b=f"[{doc_ev.evidence_id}] {doc_ev.title}",
                                value_b=f"{doc_val:,.2f}",
                                severity="high" if diff_ratio > 0.15 else "medium",
                                description=(
                                    f"Discrepancy detected between structured data "
                                    f"({sql_ev.evidence_id}: {sql_val:,.2f}) and document text "
                                    f"({doc_ev.evidence_id}: {doc_val:,.2f})."
                                ),
                            )
                        )

        # Deduplicate conflicts on source pair & values
        seen: set[tuple[str, str, str, str]] = set()
        deduped: list[DataConflict] = []
        for c in conflicts:
            key = (c.source_a, c.source_b, str(c.value_a), str(c.value_b))
            if key not in seen:
                seen.add(key)
                deduped.append(c)

        return deduped

    def _parse_number(self, text: str) -> float | None:
        """Parse currency or metric string into a standard float."""
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
        except ValueError:
            return None
