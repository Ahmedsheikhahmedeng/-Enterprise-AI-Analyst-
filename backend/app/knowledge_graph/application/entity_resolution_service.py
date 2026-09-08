"""Deterministic multi-tier entity resolution service supporting Arabic, Turkish, and English."""

import uuid
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import GraphNodeType, ResolutionStatus
from app.knowledge_graph.domain.models import EntityResolutionResult
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.observability.instrumentation.knowledge_graph import (
    get_knowledge_graph_instrumentation,
)
from app.semantic.application.normalizer import SemanticTextNormalizer


class EntityResolutionService:
    """Resolves natural language entity mentions to canonical knowledge graph entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)
        self.instrumentation = get_knowledge_graph_instrumentation()

    async def resolve(
        self,
        text: str,
        organization_id: UUID,
    ) -> EntityResolutionResult:
        """Execute deterministic cascade to identify referenced entity node."""
        cleaned = text.strip()
        if not cleaned:
            return EntityResolutionResult(
                status=ResolutionStatus.UNKNOWN,
                entity_node_id=None,
                entity_name=None,
                confidence=0.0,
                candidate_ids=[],
                reason="Input text is empty",
            )

        # 1. Exact UUID match
        try:
            val_uuid = uuid.UUID(cleaned)
            node = await self.repo.get_node(val_uuid, organization_id)
            if node and node.node_type == GraphNodeType.ENTITY:
                return EntityResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    entity_node_id=node.id,
                    entity_name=node.name,
                    confidence=1.0,
                    candidate_ids=[node.id],
                    reason="Exact UUID match",
                )
        except (ValueError, AttributeError):
            pass

        norm_text = SemanticTextNormalizer.normalize(cleaned)

        # 2. Exact Normalized Name Match
        node_exact = await self.repo.get_node_by_normalized_name(
            organization_id=organization_id,
            normalized_name=norm_text,
            node_type=GraphNodeType.ENTITY,
        )
        if node_exact:
            return EntityResolutionResult(
                status=ResolutionStatus.RESOLVED,
                entity_node_id=node_exact.id,
                entity_name=node_exact.name,
                confidence=1.0,
                candidate_ids=[node_exact.id],
                reason="Exact normalized entity name match",
            )

        # 3. Verified Alias Match
        matching_aliases = await self.repo.find_aliases_by_normalized_name(
            organization_id, norm_text
        )
        verified_aliases = [a for a in matching_aliases if a.is_verified]
        if verified_aliases:
            entity_id = verified_aliases[0].entity_node_id
            node = await self.repo.get_node(entity_id, organization_id)
            return EntityResolutionResult(
                status=ResolutionStatus.RESOLVED,
                entity_node_id=entity_id,
                entity_name=node.name if node else None,
                confidence=0.95,
                candidate_ids=[a.entity_node_id for a in verified_aliases],
                reason="Verified alias match",
            )

        # 4. Unverified Alias / Synonym Match
        if matching_aliases:
            entity_ids = list({a.entity_node_id for a in matching_aliases})
            if len(entity_ids) == 1:
                node = await self.repo.get_node(entity_ids[0], organization_id)
                return EntityResolutionResult(
                    status=ResolutionStatus.RESOLVED,
                    entity_node_id=entity_ids[0],
                    entity_name=node.name if node else None,
                    confidence=0.85,
                    candidate_ids=entity_ids,
                    reason="Unverified alias / synonym match",
                )
            else:
                self.instrumentation.record_resolution_ambiguous(GraphNodeType.ENTITY.value)
                return EntityResolutionResult(
                    status=ResolutionStatus.AMBIGUOUS,
                    entity_node_id=None,
                    entity_name=None,
                    confidence=0.5,
                    candidate_ids=entity_ids,
                    reason="Multiple candidate entities match alias",
                )

        # 5. Lexical Similarity
        all_entities = await self.repo.list_nodes(
            organization_id=organization_id,
            node_type=GraphNodeType.ENTITY,
            limit=500,
        )

        candidates: list[tuple[UUID, str, float]] = []
        for ent in all_entities:
            score = self._lexical_similarity(norm_text, ent.normalized_name)
            if score >= 0.70:
                candidates.append((ent.id, ent.name, score))

        if candidates:
            # Sort by score descending
            candidates.sort(key=lambda x: x[2], reverse=True)
            top_id, top_name, top_score = candidates[0]

            # Check if there is ambiguity (second candidate within 0.05 of top candidate)
            if len(candidates) > 1 and (top_score - candidates[1][2]) < 0.05:
                self.instrumentation.record_resolution_ambiguous(GraphNodeType.ENTITY.value)
                return EntityResolutionResult(
                    status=ResolutionStatus.AMBIGUOUS,
                    entity_node_id=None,
                    entity_name=None,
                    confidence=round(top_score, 2),
                    candidate_ids=[c[0] for c in candidates[:3]],
                    reason="Multiple entities exhibit similar lexical similarity",
                )

            return EntityResolutionResult(
                status=ResolutionStatus.RESOLVED,
                entity_node_id=top_id,
                entity_name=top_name,
                confidence=round(top_score, 2),
                candidate_ids=[top_id],
                reason=f"Lexical similarity match ({round(top_score, 2)})",
            )

        # 6. Unknown / Unresolved
        return EntityResolutionResult(
            status=ResolutionStatus.UNKNOWN,
            entity_node_id=None,
            entity_name=None,
            confidence=0.0,
            candidate_ids=[],
            reason="No candidate entity satisfied resolution thresholds",
        )

    @staticmethod
    def _lexical_similarity(str1: str, str2: str) -> float:
        """Compute string similarity combining token overlap and Levenshtein ratio."""
        if str1 == str2:
            return 1.0
        if str1 in str2 or str2 in str1:
            return 0.85
        # Token Jaccard
        tokens1 = set(str1.split())
        tokens2 = set(str2.split())
        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2) if (tokens1 and tokens2) else 0.0
        # SequenceMatcher ratio
        ratio = SequenceMatcher(None, str1, str2).ratio()
        return max(jaccard, ratio)
