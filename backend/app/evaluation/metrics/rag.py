"""Evaluation metrics assessing Retrieval-Augmented Generation (RAG) quality."""

import re
from collections.abc import Sequence

from app.evaluation.models import RAGMetrics


def extract_claims(text: str) -> list[str]:
    """Segment an answer text into testable factual claim statements."""
    if not text:
        return []
    # Split by periods, semicolons, or line breaks, stripping citation tokens
    raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    cleaned: list[str] = []
    for s in raw_sentences:
        clean_s = re.sub(r"\[[A-Za-z0-9_-]+\]", "", s).strip()
        if len(clean_s) > 10:
            cleaned.append(clean_s)
    return cleaned if cleaned else [text.strip()]


def context_recall(retrieved_contexts: Sequence[str], ground_truth_facts: Sequence[str]) -> float:
    """Evaluate proportion of ground-truth facts represented in retrieved contexts."""
    if not ground_truth_facts:
        return 1.0
    if not retrieved_contexts:
        return 0.0

    combined_context = " ".join(retrieved_contexts).lower()
    hits = 0
    for fact in ground_truth_facts:
        # Check if fact tokens substantially appear in context
        fact_words = [w.lower() for w in re.findall(r"\b\w{3,}\b", fact)]
        if not fact_words:
            continue
        matched_words = sum(1 for w in fact_words if w in combined_context)
        if matched_words / len(fact_words) >= 0.6:
            hits += 1

    return hits / len(ground_truth_facts)


def context_precision(retrieved_chunks: Sequence[str], relevant_chunks: Sequence[str]) -> float:
    """Evaluate precision of retrieved context chunks against known relevant identifiers."""
    if not retrieved_chunks:
        return 0.0
    if not relevant_chunks:
        return 1.0
    rel_set = set(relevant_chunks)
    hits = sum(1 for chunk in retrieved_chunks if chunk in rel_set)
    return hits / len(retrieved_chunks)


def answer_relevance(query: str, answer: str) -> float:
    """Measure lexical and intent alignment between user query and synthesized answer."""
    if not query or not answer:
        return 0.0

    query_tokens = set(re.findall(r"\b\w{3,}\b", query.lower()))
    if not query_tokens:
        return 1.0

    answer_lower = answer.lower()
    matched = sum(1 for token in query_tokens if token in answer_lower)
    return min(1.0, matched / len(query_tokens))


def faithfulness(answer_claims: Sequence[str], evidence_texts: Sequence[str]) -> float:
    """Evaluate ratio of answer claims corroborated by retrieved evidence."""
    if not answer_claims:
        return 1.0
    if not evidence_texts:
        return 0.0

    combined_evidence = " ".join(evidence_texts).lower()
    corroborated = 0

    for claim in answer_claims:
        claim_tokens = [w.lower() for w in re.findall(r"\b\w{3,}\b", claim)]
        if not claim_tokens:
            continue
        matched = sum(1 for w in claim_tokens if w in combined_evidence)
        if (matched / len(claim_tokens)) >= 0.5:
            corroborated += 1

    return corroborated / len(answer_claims)


def compute_rag_metrics(
    query: str,
    answer: str,
    retrieved_contexts: Sequence[str],
    retrieved_chunks: Sequence[str],
    relevant_chunks: Sequence[str],
    ground_truth_facts: Sequence[str] | None = None,
) -> RAGMetrics:
    """Compute RAG evaluation suite for an execution run."""
    claims = extract_claims(answer)
    facts = ground_truth_facts or claims

    return RAGMetrics(
        context_recall=context_recall(retrieved_contexts, facts),
        context_precision=context_precision(retrieved_chunks, relevant_chunks),
        answer_relevance=answer_relevance(query, answer),
        faithfulness=faithfulness(claims, retrieved_contexts),
    )
