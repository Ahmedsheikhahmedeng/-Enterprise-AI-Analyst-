"""Synchronizes Semantic Catalog objects into the canonical Knowledge Graph."""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.domain.enums import (
    GraphEdgeType,
    GraphNodeType,
    GraphStatus,
    RelationshipConfidenceTier,
)
from app.knowledge_graph.infrastructure.repository import KnowledgeGraphRepository
from app.models.dataset import Dataset, DatasetColumn
from app.models.semantic import (
    BusinessTerm,
    SemanticColumnMapping,
    SemanticDimension,
    SemanticEntity,
    SemanticMetric,
    SemanticRelationship,
    SemanticSynonym,
)
from app.semantic.application.normalizer import SemanticTextNormalizer

logger = logging.getLogger(__name__)


@dataclass
class GraphSyncSummary:
    """Summary of items added or updated during synchronization."""

    nodes_created: int = 0
    edges_created: int = 0
    aliases_created: int = 0
    skipped: int = 0


class GraphSyncService:
    """Idempotently syncs entities, metrics, dimensions, datasets, and mappings to graph."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = KnowledgeGraphRepository(session)

    async def sync_organization_graph(self, organization_id: UUID) -> GraphSyncSummary:
        """Run idempotent sync of all semantic assets for a tenant organization."""
        summary = GraphSyncSummary()

        # 1. Sync Business Terms
        await self._sync_business_terms(organization_id, summary)

        # 2. Sync Datasets and Dataset Columns
        await self._sync_datasets_and_columns(organization_id, summary)

        # 3. Sync Semantic Entities
        entity_node_map = await self._sync_entities(organization_id, summary)

        # 4. Sync Semantic Relationships
        await self._sync_relationships(organization_id, entity_node_map, summary)

        # 5. Sync Semantic Metrics
        metric_node_map = await self._sync_metrics(organization_id, summary)

        # 6. Sync Semantic Dimensions
        dim_node_map = await self._sync_dimensions(organization_id, summary)

        # 7. Sync Column Mappings
        await self._sync_column_mappings(
            organization_id, metric_node_map, dim_node_map, entity_node_map, summary
        )

        # 8. Sync Synonyms to GraphEntityAliases
        await self._sync_synonyms(organization_id, summary)

        return summary

    async def _sync_business_terms(self, organization_id: UUID, summary: GraphSyncSummary) -> None:
        stmt = select(BusinessTerm).where(BusinessTerm.organization_id == organization_id)
        result = await self.session.execute(stmt)
        terms = result.scalars().all()

        for term in terms:
            existing = await self.repo.get_node_by_source(organization_id, "business_term", term.id)
            if not existing:
                status = GraphStatus.PUBLISHED if term.status == "published" else GraphStatus.DRAFT
                await self.repo.create_node(
                    organization_id=organization_id,
                    node_type=GraphNodeType.TERM,
                    name=term.name,
                    normalized_name=term.normalized_name,
                    source_object_type="business_term",
                    source_object_id=term.id,
                    metadata={"category": term.category, "definition": term.definition},
                    status=status,
                )
                summary.nodes_created += 1
            else:
                summary.skipped += 1

    async def _sync_datasets_and_columns(
        self, organization_id: UUID, summary: GraphSyncSummary
    ) -> None:
        stmt = select(Dataset).where(Dataset.organization_id == organization_id)
        result = await self.session.execute(stmt)
        datasets = result.scalars().all()

        for ds in datasets:
            ds_node = await self.repo.get_node_by_source(organization_id, "dataset", ds.id)
            if not ds_node:
                norm_ds_name = SemanticTextNormalizer.normalize(ds.name)
                ds_node = await self.repo.create_node(
                    organization_id=organization_id,
                    node_type=GraphNodeType.DATASET,
                    name=ds.name,
                    normalized_name=norm_ds_name,
                    source_object_type="dataset",
                    source_object_id=ds.id,
                    metadata={"dataset_type": getattr(ds, "dataset_type", "TABLE")},
                    status=GraphStatus.PUBLISHED,
                )
                summary.nodes_created += 1

            # Sync columns
            col_stmt = select(DatasetColumn).where(DatasetColumn.dataset_id == ds.id)
            col_result = await self.session.execute(col_stmt)
            columns = col_result.scalars().all()

            for col in columns:
                col_node = await self.repo.get_node_by_source(
                    organization_id, "dataset_column", col.id
                )
                if not col_node:
                    norm_col_name = SemanticTextNormalizer.normalize(col.name)
                    col_node = await self.repo.create_node(
                        organization_id=organization_id,
                        node_type=GraphNodeType.DATASET_COLUMN,
                        name=f"{ds.name}.{col.name}",
                        normalized_name=norm_col_name,
                        source_object_type="dataset_column",
                        source_object_id=col.id,
                        metadata={"data_type": str(col.data_type)},
                        status=GraphStatus.PUBLISHED,
                    )
                    summary.nodes_created += 1

                    # Create HAS_COLUMN edge
                    await self.repo.create_edge(
                        organization_id=organization_id,
                        source_node_id=ds_node.id,
                        target_node_id=col_node.id,
                        edge_type=GraphEdgeType.HAS_COLUMN,
                        confidence=RelationshipConfidenceTier.VERIFIED.value,
                        is_verified=True,
                        status=GraphStatus.PUBLISHED,
                        source_object_type="dataset_column",
                        source_object_id=col.id,
                    )
                    summary.edges_created += 1

    async def _sync_entities(
        self, organization_id: UUID, summary: GraphSyncSummary
    ) -> dict[UUID, UUID]:
        entity_node_map: dict[UUID, UUID] = {}
        stmt = select(SemanticEntity).where(SemanticEntity.organization_id == organization_id)
        result = await self.session.execute(stmt)
        entities = result.scalars().all()

        for ent in entities:
            existing = await self.repo.get_node_by_source(
                organization_id, "semantic_entity", ent.id
            )
            if not existing:
                status = GraphStatus.PUBLISHED if ent.status == "published" else GraphStatus.DRAFT
                node = await self.repo.create_node(
                    organization_id=organization_id,
                    node_type=GraphNodeType.ENTITY,
                    name=ent.name,
                    normalized_name=ent.normalized_name,
                    source_object_type="semantic_entity",
                    source_object_id=ent.id,
                    metadata={"primary_key": ent.primary_key, "dataset_id": str(ent.dataset_id)},
                    status=status,
                )
                entity_node_map[ent.id] = node.id
                summary.nodes_created += 1
            else:
                entity_node_map[ent.id] = existing.id
                summary.skipped += 1

        return entity_node_map

    async def _sync_relationships(
        self,
        organization_id: UUID,
        entity_node_map: dict[UUID, UUID],
        summary: GraphSyncSummary,
    ) -> None:
        stmt = select(SemanticRelationship).where(
            SemanticRelationship.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        rels = result.scalars().all()

        for rel in rels:
            src_node_id = entity_node_map.get(rel.from_entity_id)
            tgt_node_id = entity_node_map.get(rel.to_entity_id)

            if not src_node_id or not tgt_node_id:
                continue

            existing_edges = await self.repo.list_edges(
                organization_id=organization_id,
                source_node_id=src_node_id,
                target_node_id=tgt_node_id,
                edge_type=GraphEdgeType.JOINS_WITH,
            )
            if not existing_edges:
                status = GraphStatus.PUBLISHED if rel.status == "published" else GraphStatus.DRAFT
                await self.repo.create_edge(
                    organization_id=organization_id,
                    source_node_id=src_node_id,
                    target_node_id=tgt_node_id,
                    edge_type=GraphEdgeType.JOINS_WITH,
                    weight=1.0,
                    confidence=RelationshipConfidenceTier.EXPLICIT.value,
                    is_verified=True,
                    status=status,
                    source_object_type="semantic_relationship",
                    source_object_id=rel.id,
                )
                summary.edges_created += 1

    async def _sync_metrics(
        self, organization_id: UUID, summary: GraphSyncSummary
    ) -> dict[UUID, UUID]:
        metric_node_map: dict[UUID, UUID] = {}
        stmt = select(SemanticMetric).where(SemanticMetric.organization_id == organization_id)
        result = await self.session.execute(stmt)
        metrics = result.scalars().all()

        for m in metrics:
            node = await self.repo.get_node_by_source(organization_id, "semantic_metric", m.id)
            if not node:
                status = GraphStatus.PUBLISHED if m.status == "published" else GraphStatus.DRAFT
                node = await self.repo.create_node(
                    organization_id=organization_id,
                    node_type=GraphNodeType.METRIC,
                    name=m.name,
                    normalized_name=m.normalized_name,
                    source_object_type="semantic_metric",
                    source_object_id=m.id,
                    metadata={"formula": m.formula, "aggregation": m.aggregation},
                    status=status,
                )
                summary.nodes_created += 1

            metric_node_map[m.id] = node.id

            # Link to Dataset if dataset_id exists
            if m.dataset_id:
                ds_node = await self.repo.get_node_by_source(
                    organization_id, "dataset", m.dataset_id
                )
                if ds_node:
                    existing = await self.repo.list_edges(
                        organization_id=organization_id,
                        source_node_id=node.id,
                        target_node_id=ds_node.id,
                        edge_type=GraphEdgeType.DERIVED_FROM,
                    )
                    if not existing:
                        await self.repo.create_edge(
                            organization_id=organization_id,
                            source_node_id=node.id,
                            target_node_id=ds_node.id,
                            edge_type=GraphEdgeType.DERIVED_FROM,
                            confidence=RelationshipConfidenceTier.EXPLICIT.value,
                            is_verified=True,
                            status=GraphStatus.PUBLISHED,
                            source_object_type="semantic_metric",
                            source_object_id=m.id,
                        )
                        summary.edges_created += 1

        return metric_node_map

    async def _sync_dimensions(
        self, organization_id: UUID, summary: GraphSyncSummary
    ) -> dict[UUID, UUID]:
        dim_node_map: dict[UUID, UUID] = {}
        stmt = select(SemanticDimension).where(SemanticDimension.organization_id == organization_id)
        result = await self.session.execute(stmt)
        dimensions = result.scalars().all()

        for d in dimensions:
            node = await self.repo.get_node_by_source(organization_id, "semantic_dimension", d.id)
            if not node:
                status = GraphStatus.PUBLISHED if d.status == "published" else GraphStatus.DRAFT
                node = await self.repo.create_node(
                    organization_id=organization_id,
                    node_type=GraphNodeType.DIMENSION,
                    name=d.name,
                    normalized_name=d.normalized_name,
                    source_object_type="semantic_dimension",
                    source_object_id=d.id,
                    metadata={"data_type": d.data_type},
                    status=status,
                )
                summary.nodes_created += 1

            dim_node_map[d.id] = node.id

            # Link to DatasetColumn
            col_node = await self.repo.get_node_by_source(
                organization_id, "dataset_column", d.column_id
            )
            if col_node:
                existing = await self.repo.list_edges(
                    organization_id=organization_id,
                    source_node_id=node.id,
                    target_node_id=col_node.id,
                    edge_type=GraphEdgeType.BELONGS_TO,
                )
                if not existing:
                    await self.repo.create_edge(
                        organization_id=organization_id,
                        source_node_id=node.id,
                        target_node_id=col_node.id,
                        edge_type=GraphEdgeType.BELONGS_TO,
                        confidence=RelationshipConfidenceTier.EXPLICIT.value,
                        is_verified=True,
                        status=GraphStatus.PUBLISHED,
                        source_object_type="semantic_dimension",
                        source_object_id=d.id,
                    )
                    summary.edges_created += 1

        return dim_node_map

    async def _sync_column_mappings(
        self,
        organization_id: UUID,
        metric_node_map: dict[UUID, UUID],
        dim_node_map: dict[UUID, UUID],
        entity_node_map: dict[UUID, UUID],
        summary: GraphSyncSummary,
    ) -> None:
        stmt = select(SemanticColumnMapping).where(
            SemanticColumnMapping.organization_id == organization_id
        )
        result = await self.session.execute(stmt)
        mappings = result.scalars().all()

        for m in mappings:
            concept_node_id = (
                metric_node_map.get(m.semantic_object_id)
                or dim_node_map.get(m.semantic_object_id)
                or entity_node_map.get(m.semantic_object_id)
            )
            if not concept_node_id:
                # Try finding node by source
                node = await self.repo.get_node_by_source(
                    organization_id, m.semantic_object_type, m.semantic_object_id
                )
                if node:
                    concept_node_id = node.id

            col_node = await self.repo.get_node_by_source(
                organization_id, "dataset_column", m.column_id
            )

            if concept_node_id and col_node:
                existing = await self.repo.list_edges(
                    organization_id=organization_id,
                    source_node_id=concept_node_id,
                    target_node_id=col_node.id,
                    edge_type=GraphEdgeType.MAPS_TO,
                )
                if not existing:
                    conf = 1.0 if m.is_verified else m.confidence
                    await self.repo.create_edge(
                        organization_id=organization_id,
                        source_node_id=concept_node_id,
                        target_node_id=col_node.id,
                        edge_type=GraphEdgeType.MAPS_TO,
                        confidence=conf,
                        is_verified=m.is_verified,
                        status=GraphStatus.PUBLISHED if m.is_verified else GraphStatus.DRAFT,
                        source_object_type="semantic_column_mapping",
                        source_object_id=m.id,
                    )
                    summary.edges_created += 1

    async def _sync_synonyms(self, organization_id: UUID, summary: GraphSyncSummary) -> None:
        stmt = select(SemanticSynonym).where(SemanticSynonym.organization_id == organization_id)
        result = await self.session.execute(stmt)
        synonyms = result.scalars().all()

        for syn in synonyms:
            node = await self.repo.get_node_by_source(
                organization_id, syn.semantic_object_type, syn.semantic_object_id
            )
            if node:
                existing_aliases = await self.repo.find_aliases_by_normalized_name(
                    organization_id, syn.normalized_synonym
                )
                already_exists = any(a.entity_node_id == node.id for a in existing_aliases)
                if not already_exists:
                    await self.repo.create_alias(
                        organization_id=organization_id,
                        entity_node_id=node.id,
                        alias=syn.synonym,
                        normalized_alias=syn.normalized_synonym,
                        language=syn.language,
                        source="synonym",
                        is_verified=True,
                    )
                    summary.aliases_created += 1
