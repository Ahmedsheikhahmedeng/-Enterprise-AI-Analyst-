"""Grounding and citation validation, phantom citation repair, and confidence scoring."""

import logging
import re

from app.rag.models import CitationReference, Evidence, GroundedAnswer

logger = logging.getLogger(__name__)


class GroundingValidator:
    """Validates citations, repairs phantom references, and computes grounding confidence."""

    _INSUFFICIENT_SIGNALS = [
        "not enough information",
        "insufficient information",
        "does not contain",
        "do not contain",
        "not contain",
        "no information",
        "not enough",
        "not available",
        "cannot answer",
        "لا توجد معلومات كافية",
        "لا أعرف",
        "لم أجد",
        "yetersiz bilgi",
        "bilgi bulunmamaktadır",
        "cevap verilememektedir",
    ]

    _CONTRADICTION_SIGNALS = [
        "conflict",
        "divergent",
        "contradict",
        "discrepancy",
        "inconsistent",
        "تضارب",
        "تناقض",
        "اختلاف في الأرقام",
        "çelişki",
        "farklılık göstermektedir",
    ]

    _CITATION_TAG_RE = re.compile(r"\[([SRE]\d+)\]")

    def validate_and_repair(
        self,
        raw_answer: str,
        claimed_evidence_ids: list[str],
        claimed_grounded: bool,
        claimed_confidence: float | None,
        available_evidence: list[Evidence],
    ) -> GroundedAnswer:
        """Validate citations against available evidence, sanitize phantom references, and score.

        Returns:
            Validated GroundedAnswer dataclass.
        """
        available_by_id = {ev.evidence_id: ev for ev in available_evidence}
        available_ids = set(available_by_id.keys())

        # 1. Check citations inside raw_answer text
        text_citations = set(self._CITATION_TAG_RE.findall(raw_answer))
        all_cited_ids = set(claimed_evidence_ids).union(text_citations)

        # 2. Filter valid vs phantom citations
        valid_ids: list[str] = []
        phantom_ids: list[str] = []
        for eid in all_cited_ids:
            if eid in available_ids:
                valid_ids.append(eid)
            else:
                phantom_ids.append(eid)

        # Sort valid IDs by evidence tag (e.g. S1, R1, E1...)
        valid_ids.sort(
            key=lambda x: (x[0], int(x[1:])) if len(x) > 1 and x[1:].isdigit() else (x, 999)
        )

        # 3. Clean up phantom citations from answer text if any exist
        repaired_answer = raw_answer
        for pid in phantom_ids:
            logger.warning("Phantom citation detected and stripped: %s", pid)
            repaired_answer = repaired_answer.replace(f"[{pid}]", "")

        # 4. Determine grounded flag
        answer_lower = repaired_answer.lower()
        has_insufficient_signal = any(sig in answer_lower for sig in self._INSUFFICIENT_SIGNALS)

        grounded = claimed_grounded and bool(valid_ids) and not has_insufficient_signal

        # 5. Check for contradiction indicators
        is_contradictory = any(sig in answer_lower for sig in self._CONTRADICTION_SIGNALS)

        # 6. Build CitationReferences
        citations: list[CitationReference] = []
        for vid in valid_ids:
            ev = available_by_id[vid]
            citations.append(
                CitationReference(
                    evidence_id=vid,
                    chunk_id=ev.chunk_id,
                    document_id=ev.document_id,
                    page_number=ev.page_number,
                    source_locator=ev.source_locator,
                    document_name=ev.document_name,
                )
            )

        # 7. Compute composite confidence
        # Factor A: Base confidence from cited evidence rerank scores
        if valid_ids:
            scores: list[float] = []
            for vid in valid_ids:
                sc = available_by_id[vid].rerank_score
                if sc is not None:
                    scores.append(sc)
            avg_score = sum(scores) / len(scores) if scores else 0.8
            # Sigmoid/linear normalization of rerank score into [0.5, 0.95]
            evidence_quality = max(0.5, min(0.95, avg_score))
        else:
            evidence_quality = 0.2

        # Factor B: Phantom penalty
        phantom_penalty = 0.15 * len(phantom_ids)

        system_grounding_conf = max(0.1, min(1.0, evidence_quality - phantom_penalty))

        if not grounded:
            system_grounding_conf = min(0.3, system_grounding_conf)
            final_conf = system_grounding_conf
        else:
            final_conf = (
                system_grounding_conf
                if claimed_confidence is None
                else round(0.6 * system_grounding_conf + 0.4 * claimed_confidence, 2)
            )

        return GroundedAnswer(
            answer=repaired_answer.strip(),
            evidence_ids=valid_ids,
            grounded=grounded,
            confidence=final_conf,
            system_grounding_confidence=round(system_grounding_conf, 2),
            model_confidence=claimed_confidence,
            is_contradictory=is_contradictory,
            citations=citations,
        )
