"""REST API endpoints for Semantic Catalog, Business Glossary, Metrics, and Semantic Layer."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestAppException, NotFoundAppException
from app.db.postgres import get_db_session
from app.models.audit import AuditLog
from app.observability.instrumentation.semantic import (
    AUDIT_SEMANTIC_MAPPING_CREATED,
    AUDIT_SEMANTIC_MAPPING_VERIFIED,
    AUDIT_SEMANTIC_METRIC_CREATED,
    AUDIT_SEMANTIC_OBJECT_PUBLISHED,
    AUDIT_SEMANTIC_TERM_CREATED,
    AUDIT_SEMANTIC_TERM_UPDATED,
)
from app.rbac.catalog import (
    PERM_SEMANTIC_CREATE,
    PERM_SEMANTIC_PUBLISH,
    PERM_SEMANTIC_READ,
    PERM_SEMANTIC_UPDATE,
    PERM_SEMANTIC_VERIFY,
)
from app.rbac.dependencies import require_permission
from app.semantic.api.schemas import (
    BusinessTermCreateRequest,
    BusinessTermResponse,
    BusinessTermUpdateRequest,
    BusinessTermVersionResponse,
    SemanticConflictResponse,
    SemanticDimensionCreateRequest,
    SemanticDimensionResponse,
    SemanticEntityCreateRequest,
    SemanticEntityResponse,
    SemanticMappingCreateRequest,
    SemanticMappingResponse,
    SemanticMetricCreateRequest,
    SemanticMetricResponse,
    SemanticPublishRequest,
    SemanticQueryPlanRequest,
    SemanticQueryPlanResponse,
    SemanticRelationshipCreateRequest,
    SemanticRelationshipResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResultResponse,
)
from app.semantic.application.conflict_detector import SemanticConflictDetector
from app.semantic.application.glossary_service import GlossaryService
from app.semantic.application.mapping_service import MappingService
from app.semantic.application.metric_service import MetricService
from app.semantic.application.query_planner import SemanticQueryPlanner
from app.semantic.application.semantic_search_service import SemanticSearchService
from app.semantic.domain.enums import SemanticStatus
from app.semantic.domain.errors import (
    InvalidMetricFormulaError,
    SemanticError,
    SemanticObjectNotFoundError,
)
from app.semantic.infrastructure.repository import SemanticRepository
from app.tenancy.context import TenantContext
from app.tenancy.dependencies import get_tenant_context

router = APIRouter(prefix="/semantic", tags=["Semantic Layer & Data Catalog"])


# -----------------------------------------------------------------------------
# 1. Semantic Search
# -----------------------------------------------------------------------------


@router.post(
    "/search",
    response_model=SemanticSearchResponse,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def search_semantic_catalog(
    payload: SemanticSearchRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticSearchResponse:
    """Hybrid search across business terms, metrics, dimensions, entities, and synonyms."""
    search_service = SemanticSearchService(db_session)
    results = await search_service.search(
        query=payload.query,
        organization_id=tenant_context.organization_id,
        limit=payload.limit,
        object_types=payload.object_types,
        only_published=payload.only_published,
    )
    items = [
        SemanticSearchResultResponse(
            object_id=r.object_id,
            object_type=r.object_type.value,
            name=r.name,
            description=r.description,
            definition=r.definition,
            status=r.status.value,
            match_source=r.match_source.value,
            score=r.score,
            is_verified=r.is_verified,
            language=r.language,
            metadata=r.metadata,
        )
        for r in results
    ]
    return SemanticSearchResponse(results=items, count=len(items))


# -----------------------------------------------------------------------------
# 2. Business Glossary Terms
# -----------------------------------------------------------------------------


@router.post(
    "/terms",
    response_model=BusinessTermResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_CREATE))],
)
async def create_business_term(
    payload: BusinessTermCreateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BusinessTermResponse:
    """Create a new business term in draft state."""
    glossary = GlossaryService(db_session)
    term = await glossary.create_term(
        organization_id=tenant_context.organization_id,
        name=payload.name,
        definition=payload.definition,
        description=payload.description,
        category=payload.category,
        owner=payload.owner,
        steward=payload.steward,
        created_by=tenant_context.user_id,
    )
    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action=AUDIT_SEMANTIC_TERM_CREATED,
        resource_type="business_term",
        resource_id=str(term.id),
        details={"name": term.name, "category": term.category},
    )
    db_session.add(audit)
    await db_session.commit()
    await db_session.refresh(term)

    return BusinessTermResponse(
        id=term.id,
        organization_id=term.organization_id,
        name=term.name,
        normalized_name=term.normalized_name,
        definition=term.definition,
        description=term.description,
        category=term.category,
        status=term.status,
        version=term.version,
        owner=term.owner,
        steward=term.steward,
        created_at=term.created_at,
        updated_at=term.updated_at,
        versions=[],
    )


@router.get(
    "/terms",
    response_model=list[BusinessTermResponse],
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def list_business_terms(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    status: SemanticStatus | None = None,
    category: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[BusinessTermResponse]:
    glossary = GlossaryService(db_session)
    terms = await glossary.list_terms(
        organization_id=tenant_context.organization_id,
        status=status,
        category=category,
        offset=offset,
        limit=limit,
    )
    return [
        BusinessTermResponse(
            id=t.id,
            organization_id=t.organization_id,
            name=t.name,
            normalized_name=t.normalized_name,
            definition=t.definition,
            description=t.description,
            category=t.category,
            status=t.status,
            version=t.version,
            owner=t.owner,
            steward=t.steward,
            created_at=t.created_at,
            updated_at=t.updated_at,
            versions=[],
        )
        for t in terms
    ]


@router.get(
    "/terms/{id}",
    response_model=BusinessTermResponse,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def get_business_term(
    id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BusinessTermResponse:
    glossary = GlossaryService(db_session)
    try:
        term = await glossary.get_term(id, tenant_context.organization_id)
    except SemanticObjectNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc

    versions = [
        BusinessTermVersionResponse(
            id=v.id,
            version=v.version,
            definition=v.definition,
            description=v.description,
            created_at=v.created_at,
        )
        for v in term.versions
    ]
    return BusinessTermResponse(
        id=term.id,
        organization_id=term.organization_id,
        name=term.name,
        normalized_name=term.normalized_name,
        definition=term.definition,
        description=term.description,
        category=term.category,
        status=term.status,
        version=term.version,
        owner=term.owner,
        steward=term.steward,
        created_at=term.created_at,
        updated_at=term.updated_at,
        versions=versions,
    )


@router.patch(
    "/terms/{id}",
    response_model=BusinessTermResponse,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_UPDATE))],
)
async def update_business_term(
    id: uuid.UUID,
    payload: BusinessTermUpdateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BusinessTermResponse:
    glossary = GlossaryService(db_session)
    try:
        term = await glossary.update_term(
            term_id=id,
            organization_id=tenant_context.organization_id,
            definition=payload.definition,
            description=payload.description,
            category=payload.category,
            owner=payload.owner,
            steward=payload.steward,
            updated_by=tenant_context.user_id,
        )
    except SemanticObjectNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action=AUDIT_SEMANTIC_TERM_UPDATED,
        resource_type="business_term",
        resource_id=str(term.id),
        details={"version": term.version},
    )
    db_session.add(audit)
    await db_session.commit()
    await db_session.refresh(term)

    return BusinessTermResponse(
        id=term.id,
        organization_id=term.organization_id,
        name=term.name,
        normalized_name=term.normalized_name,
        definition=term.definition,
        description=term.description,
        category=term.category,
        status=term.status,
        version=term.version,
        owner=term.owner,
        steward=term.steward,
        created_at=term.created_at,
        updated_at=term.updated_at,
        versions=[],
    )


# -----------------------------------------------------------------------------
# 3. Semantic Metrics
# -----------------------------------------------------------------------------


@router.post(
    "/metrics",
    response_model=SemanticMetricResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_CREATE))],
)
async def create_semantic_metric(
    payload: SemanticMetricCreateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticMetricResponse:
    metric_svc = MetricService(db_session)
    try:
        metric = await metric_svc.create_metric(
            organization_id=tenant_context.organization_id,
            name=payload.name,
            definition=payload.definition,
            formula=payload.formula,
            aggregation=payload.aggregation.value,
            display_name=payload.display_name,
            description=payload.description,
            grain=payload.grain,
            filters=payload.filters,
            unit=payload.unit,
            dataset_id=payload.dataset_id,
            created_by=tenant_context.user_id,
        )
    except InvalidMetricFormulaError as exc:
        raise BadRequestAppException(str(exc)) from exc

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action=AUDIT_SEMANTIC_METRIC_CREATED,
        resource_type="semantic_metric",
        resource_id=str(metric.id),
        details={"name": metric.name, "formula": metric.formula},
    )
    db_session.add(audit)
    await db_session.commit()
    await db_session.refresh(metric)

    return SemanticMetricResponse(
        id=metric.id,
        organization_id=metric.organization_id,
        name=metric.name,
        normalized_name=metric.normalized_name,
        display_name=metric.display_name,
        description=metric.description,
        definition=metric.definition,
        formula=metric.formula,
        aggregation=metric.aggregation,
        grain=metric.grain,
        filters=metric.filters or [],
        unit=metric.unit,
        dataset_id=metric.dataset_id,
        status=metric.status,
        version=metric.version,
        created_at=metric.created_at,
        updated_at=metric.updated_at,
    )


@router.get(
    "/metrics",
    response_model=list[SemanticMetricResponse],
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def list_semantic_metrics(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    status: SemanticStatus | None = None,
    dataset_id: uuid.UUID | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[SemanticMetricResponse]:
    metric_svc = MetricService(db_session)
    metrics = await metric_svc.list_metrics(
        organization_id=tenant_context.organization_id,
        status=status,
        dataset_id=dataset_id,
        offset=offset,
        limit=limit,
    )
    return [
        SemanticMetricResponse(
            id=m.id,
            organization_id=m.organization_id,
            name=m.name,
            normalized_name=m.normalized_name,
            display_name=m.display_name,
            description=m.description,
            definition=m.definition,
            formula=m.formula,
            aggregation=m.aggregation,
            grain=m.grain,
            filters=m.filters or [],
            unit=m.unit,
            dataset_id=m.dataset_id,
            status=m.status,
            version=m.version,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in metrics
    ]


@router.get(
    "/metrics/{id}",
    response_model=SemanticMetricResponse,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def get_semantic_metric(
    id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticMetricResponse:
    metric_svc = MetricService(db_session)
    try:
        m = await metric_svc.get_metric(id, tenant_context.organization_id)
    except SemanticObjectNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc

    return SemanticMetricResponse(
        id=m.id,
        organization_id=m.organization_id,
        name=m.name,
        normalized_name=m.normalized_name,
        display_name=m.display_name,
        description=m.description,
        definition=m.definition,
        formula=m.formula,
        aggregation=m.aggregation,
        grain=m.grain,
        filters=m.filters or [],
        unit=m.unit,
        dataset_id=m.dataset_id,
        status=m.status,
        version=m.version,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


# -----------------------------------------------------------------------------
# 4. Dimensions & Entities
# -----------------------------------------------------------------------------


@router.post(
    "/dimensions",
    response_model=SemanticDimensionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_CREATE))],
)
async def create_semantic_dimension(
    payload: SemanticDimensionCreateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticDimensionResponse:
    repo = SemanticRepository(db_session)
    dim = await repo.create_dimension(
        organization_id=tenant_context.organization_id,
        dataset_id=payload.dataset_id,
        column_id=payload.column_id,
        name=payload.name,
        data_type=payload.data_type,
        description=payload.description,
        hierarchy=payload.hierarchy,
        created_by=tenant_context.user_id,
    )
    await db_session.commit()
    await db_session.refresh(dim)
    return SemanticDimensionResponse(
        id=dim.id,
        organization_id=dim.organization_id,
        dataset_id=dim.dataset_id,
        column_id=dim.column_id,
        name=dim.name,
        normalized_name=dim.normalized_name,
        description=dim.description,
        data_type=dim.data_type,
        hierarchy=dim.hierarchy or [],
        status=dim.status,
        created_at=dim.created_at,
    )


@router.get(
    "/dimensions",
    response_model=list[SemanticDimensionResponse],
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def list_semantic_dimensions(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    dataset_id: uuid.UUID | None = None,
) -> list[SemanticDimensionResponse]:
    repo = SemanticRepository(db_session)
    dims = await repo.list_dimensions(
        organization_id=tenant_context.organization_id,
        dataset_id=dataset_id,
    )
    return [
        SemanticDimensionResponse(
            id=d.id,
            organization_id=d.organization_id,
            dataset_id=d.dataset_id,
            column_id=d.column_id,
            name=d.name,
            normalized_name=d.normalized_name,
            description=d.description,
            data_type=d.data_type,
            hierarchy=d.hierarchy or [],
            status=d.status,
            created_at=d.created_at,
        )
        for d in dims
    ]


@router.post(
    "/entities",
    response_model=SemanticEntityResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_CREATE))],
)
async def create_semantic_entity(
    payload: SemanticEntityCreateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticEntityResponse:
    repo = SemanticRepository(db_session)
    ent = await repo.create_entity(
        organization_id=tenant_context.organization_id,
        dataset_id=payload.dataset_id,
        name=payload.name,
        primary_key=payload.primary_key,
        description=payload.description,
        display_name_column=payload.display_name_column,
        created_by=tenant_context.user_id,
    )
    await db_session.commit()
    await db_session.refresh(ent)
    return SemanticEntityResponse(
        id=ent.id,
        organization_id=ent.organization_id,
        dataset_id=ent.dataset_id,
        name=ent.name,
        normalized_name=ent.normalized_name,
        primary_key=ent.primary_key,
        display_name_column=ent.display_name_column,
        description=ent.description,
        status=ent.status,
        created_at=ent.created_at,
    )


@router.get(
    "/entities",
    response_model=list[SemanticEntityResponse],
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def list_semantic_entities(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SemanticEntityResponse]:
    repo = SemanticRepository(db_session)
    ents = await repo.list_entities(organization_id=tenant_context.organization_id)
    return [
        SemanticEntityResponse(
            id=e.id,
            organization_id=e.organization_id,
            dataset_id=e.dataset_id,
            name=e.name,
            normalized_name=e.normalized_name,
            primary_key=e.primary_key,
            display_name_column=e.display_name_column,
            description=e.description,
            status=e.status,
            created_at=e.created_at,
        )
        for e in ents
    ]


@router.post(
    "/relationships",
    response_model=SemanticRelationshipResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_CREATE))],
)
async def create_semantic_relationship(
    payload: SemanticRelationshipCreateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticRelationshipResponse:
    repo = SemanticRepository(db_session)
    rel = await repo.create_relationship(
        organization_id=tenant_context.organization_id,
        name=payload.name,
        from_entity_id=payload.from_entity_id,
        to_entity_id=payload.to_entity_id,
        relationship_type=payload.relationship_type.value,
        from_column=payload.from_column,
        to_column=payload.to_column,
        created_by=tenant_context.user_id,
    )
    await db_session.commit()
    await db_session.refresh(rel)
    return SemanticRelationshipResponse(
        id=rel.id,
        organization_id=rel.organization_id,
        name=rel.name,
        from_entity_id=rel.from_entity_id,
        to_entity_id=rel.to_entity_id,
        relationship_type=rel.relationship_type,
        from_column=rel.from_column,
        to_column=rel.to_column,
        status=rel.status,
        created_at=rel.created_at,
    )


@router.get(
    "/relationships",
    response_model=list[SemanticRelationshipResponse],
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def list_semantic_relationships(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    entity_id: uuid.UUID | None = None,
) -> list[SemanticRelationshipResponse]:
    repo = SemanticRepository(db_session)
    rels = await repo.list_relationships(
        organization_id=tenant_context.organization_id,
        entity_id=entity_id,
    )
    return [
        SemanticRelationshipResponse(
            id=r.id,
            organization_id=r.organization_id,
            name=r.name,
            from_entity_id=r.from_entity_id,
            to_entity_id=r.to_entity_id,
            relationship_type=r.relationship_type,
            from_column=r.from_column,
            to_column=r.to_column,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rels
    ]


# -----------------------------------------------------------------------------
# 5. Column Mappings & Verification
# -----------------------------------------------------------------------------


@router.post(
    "/mappings",
    response_model=SemanticMappingResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_CREATE))],
)
async def create_semantic_mapping(
    payload: SemanticMappingCreateRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticMappingResponse:
    mapping_svc = MappingService(db_session)
    try:
        mapping = await mapping_svc.create_mapping(
            organization_id=tenant_context.organization_id,
            semantic_object_type=payload.semantic_object_type.value,
            semantic_object_id=payload.semantic_object_id,
            dataset_id=payload.dataset_id,
            column_id=payload.column_id,
            dataset_version_id=payload.dataset_version_id,
            mapping_type=payload.mapping_type.value,
            confidence=payload.confidence,
            is_verified=False,
        )
    except SemanticError as exc:
        raise BadRequestAppException(str(exc)) from exc

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action=AUDIT_SEMANTIC_MAPPING_CREATED,
        resource_type="semantic_column_mapping",
        resource_id=str(mapping.id),
        details={"dataset_id": str(mapping.dataset_id), "column_id": str(mapping.column_id)},
    )
    db_session.add(audit)
    await db_session.commit()
    await db_session.refresh(mapping)

    return SemanticMappingResponse(
        id=mapping.id,
        organization_id=mapping.organization_id,
        semantic_object_type=mapping.semantic_object_type,
        semantic_object_id=mapping.semantic_object_id,
        dataset_id=mapping.dataset_id,
        column_id=mapping.column_id,
        mapping_type=mapping.mapping_type,
        confidence=mapping.confidence,
        is_verified=mapping.is_verified,
        verified_by=mapping.verified_by,
        verified_at=mapping.verified_at,
        created_at=mapping.created_at,
    )


@router.post(
    "/mappings/{id}/verify",
    response_model=SemanticMappingResponse,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_VERIFY))],
)
async def verify_semantic_mapping(
    id: uuid.UUID,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticMappingResponse:
    mapping_svc = MappingService(db_session)
    try:
        mapping = await mapping_svc.verify_mapping(
            mapping_id=id,
            organization_id=tenant_context.organization_id,
            verified_by=tenant_context.user_id or uuid.uuid4(),
        )
    except SemanticObjectNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action=AUDIT_SEMANTIC_MAPPING_VERIFIED,
        resource_type="semantic_column_mapping",
        resource_id=str(mapping.id),
        details={"is_verified": True},
    )
    db_session.add(audit)
    await db_session.commit()
    await db_session.refresh(mapping)

    return SemanticMappingResponse(
        id=mapping.id,
        organization_id=mapping.organization_id,
        semantic_object_type=mapping.semantic_object_type,
        semantic_object_id=mapping.semantic_object_id,
        dataset_id=mapping.dataset_id,
        column_id=mapping.column_id,
        mapping_type=mapping.mapping_type,
        confidence=mapping.confidence,
        is_verified=mapping.is_verified,
        verified_by=mapping.verified_by,
        verified_at=mapping.verified_at,
        created_at=mapping.created_at,
    )


# -----------------------------------------------------------------------------
# 6. Publishing Lifecycle
# -----------------------------------------------------------------------------


@router.post(
    "/{id}/publish",
    response_model=dict[str, Any],
    dependencies=[Depends(require_permission(PERM_SEMANTIC_PUBLISH))],
)
async def publish_semantic_object(
    id: uuid.UUID,
    payload: SemanticPublishRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    repo = SemanticRepository(db_session)
    try:
        await repo.publish_object(
            object_type=payload.object_type.value,
            object_id=id,
            organization_id=tenant_context.organization_id,
            target_status=payload.target_status,
        )
    except SemanticObjectNotFoundError as exc:
        raise NotFoundAppException(str(exc)) from exc

    audit = AuditLog(
        id=uuid.uuid4(),
        organization_id=tenant_context.organization_id,
        user_id=tenant_context.user_id,
        action=AUDIT_SEMANTIC_OBJECT_PUBLISHED,
        resource_type=payload.object_type.value,
        resource_id=str(id),
        details={"target_status": payload.target_status.value},
    )
    db_session.add(audit)
    await db_session.commit()

    return {"id": str(id), "status": payload.target_status.value, "success": True}


# -----------------------------------------------------------------------------
# 7. Semantic Query Planning
# -----------------------------------------------------------------------------


@router.post(
    "/query-plan",
    response_model=SemanticQueryPlanResponse,
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def generate_semantic_query_plan(
    payload: SemanticQueryPlanRequest,
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SemanticQueryPlanResponse:
    planner = SemanticQueryPlanner(db_session)
    plan = await planner.plan_query(
        question=payload.question,
        organization_id=tenant_context.organization_id,
        target_dataset_id=payload.dataset_id,
    )
    return SemanticQueryPlanResponse(
        question=plan.question,
        is_authoritative=plan.is_authoritative,
        dataset_id=plan.dataset_id,
        sql_hint=plan.sql_hint,
        resolved_metrics=[m.model_dump(mode="json") for m in plan.resolved_metrics],
        resolved_dimensions=[d.model_dump(mode="json") for d in plan.resolved_dimensions],
        provenance=plan.provenance,
    )


# -----------------------------------------------------------------------------
# 8. Conflicts
# -----------------------------------------------------------------------------


@router.get(
    "/conflicts",
    response_model=list[SemanticConflictResponse],
    dependencies=[Depends(require_permission(PERM_SEMANTIC_READ))],
)
async def list_semantic_conflicts(
    tenant_context: Annotated[TenantContext, Depends(get_tenant_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SemanticConflictResponse]:
    detector = SemanticConflictDetector(db_session)
    # Check for new conflicts
    await detector.detect_metric_conflicts(tenant_context.organization_id)
    conflicts = await detector.list_unresolved_conflicts(tenant_context.organization_id)
    return [
        SemanticConflictResponse(
            id=c.id,
            organization_id=c.organization_id,
            object_type=c.object_type,
            object_ids=c.object_ids,
            severity=c.severity,
            reason=c.reason,
            is_resolved=c.is_resolved,
            created_at=c.created_at,
        )
        for c in conflicts
    ]
