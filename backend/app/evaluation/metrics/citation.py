"""Metrics evaluating citation correctness, precision, coverage, and phantom citations."""

import re
from collections.abc import Sequence

from app.evaluation.models import CitationMetrics


def extract_citations_from_text(text: str) -> list[str]:
    """Extract evidence citation tokens (e.g. [S1], [R2], [E1]) from text."""
    if not text:
        return []
    return re.findall(r"\[([A-Za-z0-9_-]+)\]", text)


def compute_citation_metrics(
    answer: str,
    actual_evidence_ids: Sequence[str],
    expected_citations: Sequence[str] | None = None,
) -> CitationMetrics:
    """Evaluate citation precision, recall, coverage, and phantom detection."""
    cited_ids = extract_citations_from_text(answer)
    known_evidence_set = set(actual_evidence_ids)

    # 1. Coverage
    claims = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", answer) if len(s.strip()) > 10]
    claims_with_citations = sum(1 for c in claims if bool(re.search(r"\[[A-Za-z0-9_-]+\]", c)))
    coverage = claims_with_citations / len(claims) if claims else 1.0

    if not cited_ids:
        # If no citations exist
        recall = 1.0 if not expected_citations else 0.0
        return CitationMetrics(
            citation_precision=1.0 if not expected_citations else 0.0,
            citation_recall=recall,
            citation_coverage=coverage,
            invalid_citation_rate=0.0,
            phantom_citation_rate=0.0,
        )

    # 2. Precision & Phantom Rate
    valid_citations = [c for c in cited_ids if c in known_evidence_set]
    phantom_citations = [c for c in cited_ids if c not in known_evidence_set]

    precision = len(valid_citations) / len(cited_ids)
    phantom_rate = len(phantom_citations) / len(cited_ids)
    invalid_rate = phantom_rate

    # 3. Recall against expected citations
    if expected_citations:
        exp_set = set(expected_citations)
        cited_set = set(cited_ids)
        hits = len(cited_set & exp_set)
        recall = hits / len(exp_set)
    else:
        recall = 1.0

    return CitationMetrics(
        citation_precision=precision,
        citation_recall=recall,
        citation_coverage=coverage,
        invalid_citation_rate=invalid_rate,
        phantom_citation_rate=phantom_rate,
    )
