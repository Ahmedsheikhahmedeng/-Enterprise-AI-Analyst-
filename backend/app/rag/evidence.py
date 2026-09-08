"""Evidence selection, tenant isolation verification, and light diversity filtering."""

import logging
from uuid import UUID

from app.rag.exceptions import RAGTenantMismatchError
from app.rag.models import Evidence
from app.retrieval.hybrid.models import HybridRetrievedChunk

logger = logging.getLogger(__name__)


class EvidenceSelector:
    """Selects, validates tenant isolation, and deduplicates retrieved candidates into Evidence."""

    def select_evidence(
        self,
        chunks: list[HybridRetrievedChunk],
        organization_id: UUID,
        top_k: int = 5,
        min_evidence_score: float = 0.0,
        max_per_document: int = 3,
    ) -> list[Evidence]:
        """Validate organization boundary and select diverse, deduplicated evidence blocks."""
        if not chunks or top_k <= 0:
            return []

        # 1. Strict Tenant Isolation Check: verify EVERY chunk belongs to organization_id
        for chunk in chunks:
            if chunk.organization_id != organization_id:
                msg = (
                    f"Cross-tenant candidate detected: chunk {chunk.chunk_id} "
                    f"belongs to org {chunk.organization_id}, expected {organization_id}."
                )
                logger.error(msg)
                raise RAGTenantMismatchError(msg)

        # 2. Score filtering by min_evidence_score (if rerank score available)
        valid_chunks: list[HybridRetrievedChunk] = []
        for chunk in chunks:
            if chunk.rerank_score is not None and chunk.rerank_score < min_evidence_score:
                continue
            valid_chunks.append(chunk)

        # 3. Deduplication by chunk_id preserving rank order
        seen_chunk_ids: set[UUID] = set()
        deduped_chunks: list[HybridRetrievedChunk] = []
        for chunk in valid_chunks:
            if chunk.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(chunk.chunk_id)
                deduped_chunks.append(chunk)

        # 4. Light Diversity: prevent single document from dominating all top_k slots
        selected_chunks: list[HybridRetrievedChunk] = []
        doc_counts: dict[UUID, int] = {}
        deferred: list[HybridRetrievedChunk] = []

        for chunk in deduped_chunks:
            count = doc_counts.get(chunk.document_id, 0)
            if count < max_per_document:
                selected_chunks.append(chunk)
                doc_counts[chunk.document_id] = count + 1
                if len(selected_chunks) >= top_k:
                    break
            else:
                deferred.append(chunk)

        # Fill remaining slots from deferred pool if needed to reach top_k
        if len(selected_chunks) < top_k and deferred:
            remaining = top_k - len(selected_chunks)
            selected_chunks.extend(deferred[:remaining])

        # 5. Convert to Evidence models with deterministic IDs (E1, E2...)
        evidence_list: list[Evidence] = []
        for idx, chunk in enumerate(selected_chunks, start=1):
            doc_name = (
                chunk.metadata.get("document_name")
                or chunk.metadata.get("file_name")
                or f"Doc-{str(chunk.document_id)[:8]}"
            )

            heading_path = None
            if chunk.heading_hierarchy:
                heading_path = " > ".join(chunk.heading_hierarchy)

            locator_parts = [f"Document: {doc_name}"]
            if chunk.page_number is not None:
                locator_parts.append(f"Page: {chunk.page_number}")
            if chunk.section:
                locator_parts.append(f"Section: {chunk.section}")
            elif heading_path:
                locator_parts.append(f"Section: {heading_path}")
            source_locator = ", ".join(locator_parts)

            # Prefer parent_text if hydrated and enriched, fallback to chunk text
            content_text = chunk.parent_text if chunk.parent_text else chunk.text

            evidence = Evidence(
                evidence_id=f"E{idx}",
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                organization_id=chunk.organization_id,
                rank=idx,
                rerank_score=chunk.rerank_score,
                text=content_text.strip(),
                page_number=chunk.page_number,
                heading_path=heading_path,
                heading_context=chunk.metadata.get("heading_context"),
                section=chunk.section,
                source_locator=source_locator,
                document_name=str(doc_name),
                parent_text=chunk.parent_text,
            )
            evidence_list.append(evidence)

        return evidence_list
