import uuid
from collections.abc import AsyncGenerator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.models import (
    AnalysisRun,
    AnalysisStep,
    AuditLog,
    Conversation,
    Dataset,
    DatasetColumn,
    DataSource,
    Document,
    DocumentChunk,
    LLMRequest,
    Message,
    Organization,
    OrganizationMember,
    Permission,
    Report,
    Role,
    RolePermission,
    UsageEvent,
    User,
)


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide isolated async database session with automatic transaction rollback."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as s:
        try:
            yield s
        finally:
            await s.rollback()
            await s.close()
    await dispose_database_engine(engine)


@pytest.mark.asyncio
async def test_complete_entity_relationship_graph(session: AsyncSession) -> None:
    """Verify end-to-end entity creation and ORM relationships for all 19 domain tables."""
    suffix = uuid.uuid4().hex[:8]

    # 1. Create Organization
    org = Organization(
        name=f"Acme Corp {suffix}",
        slug=f"acme-{suffix}",
    )
    session.add(org)
    await session.flush()
    assert org.id is not None

    # 2. Create User
    user = User(
        email=f"analyst_{suffix}@acme.com",
        password_hash="argon2_hashed_secret",
        first_name="Jane",
        last_name="Doe",
    )
    session.add(user)
    await session.flush()
    assert user.id is not None

    # 3. Create Role & Permission
    role = Role(
        organization_id=org.id,
        name=f"Lead Analyst {suffix}",
        description="Senior business analyst role",
    )
    permission = Permission(
        name=f"documents.manage.{suffix}",
        description="Full document control",
    )
    session.add_all([role, permission])
    await session.flush()

    # 4. RolePermission Association
    role_perm = RolePermission(
        role_id=role.id,
        permission_id=permission.id,
    )
    session.add(role_perm)
    await session.flush()

    # 5. OrganizationMember
    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role_id=role.id,
    )
    session.add(member)
    await session.flush()

    # 6. Document & DocumentChunk
    doc = Document(
        organization_id=org.id,
        name="Q2 Earnings Report",
        original_filename="q2_earnings.pdf",
        mime_type="application/pdf",
        file_size=1048576,
        storage_key=f"org_{org.id}/docs/q2.pdf",
        status="indexed",
        created_by=user.id,
    )
    session.add(doc)
    await session.flush()

    chunk = DocumentChunk(
        organization_id=org.id,
        document_id=doc.id,
        chunk_index=0,
        content="Q2 revenue exceeded target by 14%.",
        page_number=1,
        section="Executive Summary",
        metadata_={"embedding_id": "vec_001"},
    )
    session.add(chunk)
    await session.flush()

    # 7. Dataset & DatasetColumn
    dataset = Dataset(
        organization_id=org.id,
        name="Quarterly Financials",
        source_type="sql_table",
        status="active",
        row_count=50000,
        created_by=user.id,
    )
    session.add(dataset)
    await session.flush()

    column = DatasetColumn(
        dataset_id=dataset.id,
        name="revenue",
        data_type="DECIMAL(15,2)",
        nullable=False,
        ordinal_position=1,
        description="Total net revenue",
    )
    session.add(column)
    await session.flush()

    # 8. DataSource
    data_source = DataSource(
        organization_id=org.id,
        name="Main PostgreSQL Warehouse",
        type="postgresql",
        status="connected",
        configuration={"host": "warehouse.internal", "port": 5432},
        created_by=user.id,
    )
    session.add(data_source)
    await session.flush()

    # 9. Conversation & Message
    conversation = Conversation(
        organization_id=org.id,
        user_id=user.id,
        title="Revenue Analysis Q2",
    )
    session.add(conversation)
    await session.flush()

    message = Message(
        conversation_id=conversation.id,
        role="user",
        content="Why did European sales contract?",
    )
    session.add(message)
    await session.flush()

    # 10. AnalysisRun & AnalysisStep
    analysis_run = AnalysisRun(
        organization_id=org.id,
        conversation_id=conversation.id,
        user_id=user.id,
        status="completed",
        query="Analyze European division variance",
    )
    session.add(analysis_run)
    await session.flush()

    step = AnalysisStep(
        analysis_run_id=analysis_run.id,
        step_type="sql_query",
        step_order=1,
        status="completed",
        input_payload={"sql": "SELECT region, sum(revenue) FROM sales GROUP BY region"},
        output_payload={"rows": [{"region": "Europe", "variance": -0.21}]},
    )
    session.add(step)
    await session.flush()

    # 11. Report
    report = Report(
        organization_id=org.id,
        created_by=user.id,
        analysis_run_id=analysis_run.id,
        title="European Sales Decline Report",
        status="published",
        content="# Executive Summary\nEuropean operations contracted by 21%.",
        metadata_={"charts": [{"type": "bar", "data": "sales_variance"}]},
    )
    session.add(report)
    await session.flush()

    # 12. AuditLog
    audit_log = AuditLog(
        organization_id=org.id,
        user_id=user.id,
        action="REPORT_PUBLISHED",
        resource_type="report",
        resource_id=str(report.id),
        metadata_={"title": report.title},
        ip_address="192.168.1.100",
    )
    session.add(audit_log)
    await session.flush()

    # 13. UsageEvent
    usage_event = UsageEvent(
        organization_id=org.id,
        user_id=user.id,
        event_type="ANALYSIS_RUN_COMPLETED",
        quantity=1,
        metadata_={"run_id": str(analysis_run.id)},
    )
    session.add(usage_event)
    await session.flush()

    # 14. LLMRequest
    llm_request = LLMRequest(
        organization_id=org.id,
        user_id=user.id,
        analysis_run_id=analysis_run.id,
        provider="openai",
        model="gpt-4o",
        input_tokens=1500,
        output_tokens=400,
        total_tokens=1900,
        estimated_cost=Decimal("0.012500"),
        latency_ms=1850,
        status="success",
    )
    session.add(llm_request)
    await session.flush()

    # 15. Verify Relationships via ORM queries
    stmt = select(Document).options(selectinload(Document.chunks)).where(Document.id == doc.id)
    retrieved_doc = (await session.execute(stmt)).scalar_one()
    assert len(retrieved_doc.chunks) == 1
    assert retrieved_doc.chunks[0].content == "Q2 revenue exceeded target by 14%."

    stmt_run = (
        select(AnalysisRun)
        .options(selectinload(AnalysisRun.steps))
        .where(AnalysisRun.id == analysis_run.id)
    )
    retrieved_run = (await session.execute(stmt_run)).scalar_one()
    assert len(retrieved_run.steps) == 1
    assert retrieved_run.steps[0].step_type == "sql_query"


@pytest.mark.asyncio
async def test_duplicate_user_email_raises_integrity_error(session: AsyncSession) -> None:
    """Verify unique constraint on users.email."""
    suffix = uuid.uuid4().hex[:8]
    email = f"duplicate_{suffix}@example.com"

    u1 = User(email=email, password_hash="hash1")
    u2 = User(email=email, password_hash="hash2")
    session.add(u1)
    await session.flush()

    session.add(u2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_duplicate_org_slug_raises_integrity_error(session: AsyncSession) -> None:
    """Verify unique constraint on organizations.slug."""
    suffix = uuid.uuid4().hex[:8]
    slug = f"dup-org-{suffix}"

    o1 = Organization(name="Org 1", slug=slug)
    o2 = Organization(name="Org 2", slug=slug)
    session.add(o1)
    await session.flush()

    session.add(o2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_duplicate_org_membership_raises_integrity_error(
    session: AsyncSession,
) -> None:
    """Verify composite unique constraint on (organization_id, user_id)."""
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org {suffix}", slug=f"org-{suffix}")
    user = User(email=f"user_{suffix}@acme.com", password_hash="hash")
    session.add_all([org, user])
    await session.flush()

    role = Role(organization_id=org.id, name=f"Role {suffix}")
    session.add(role)
    await session.flush()

    m1 = OrganizationMember(organization_id=org.id, user_id=user.id, role_id=role.id)
    m2 = OrganizationMember(organization_id=org.id, user_id=user.id, role_id=role.id)
    session.add(m1)
    await session.flush()

    session.add(m2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_duplicate_dataset_column_name_raises_integrity_error(
    session: AsyncSession,
) -> None:
    """Verify composite unique constraint on (dataset_id, name)."""
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org {suffix}", slug=f"org-{suffix}")
    session.add(org)
    await session.flush()

    dataset = Dataset(organization_id=org.id, name="Sales", source_type="sql")
    session.add(dataset)
    await session.flush()

    c1 = DatasetColumn(dataset_id=dataset.id, name="amount", data_type="INT", ordinal_position=1)
    c2 = DatasetColumn(dataset_id=dataset.id, name="amount", data_type="INT", ordinal_position=2)
    session.add(c1)
    await session.flush()

    session.add(c2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_duplicate_analysis_step_order_raises_integrity_error(
    session: AsyncSession,
) -> None:
    """Verify composite unique constraint on (analysis_run_id, step_order)."""
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Org {suffix}", slug=f"org-{suffix}")
    user = User(email=f"u_{suffix}@test.com", password_hash="h")
    session.add_all([org, user])
    await session.flush()

    run = AnalysisRun(organization_id=org.id, user_id=user.id, query="Test Query")
    session.add(run)
    await session.flush()

    s1 = AnalysisStep(analysis_run_id=run.id, step_type="route", step_order=1)
    s2 = AnalysisStep(analysis_run_id=run.id, step_type="plan", step_order=1)
    session.add(s1)
    await session.flush()

    session.add(s2)
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_tenant_isolation_query_separation(session: AsyncSession) -> None:
    """Verify queries scoped by organization_id enforce strict tenant boundary separation."""
    suffix = uuid.uuid4().hex[:8]

    # Create Organization A and Document A
    org_a = Organization(name=f"Tenant A {suffix}", slug=f"tenant-a-{suffix}")
    session.add(org_a)
    await session.flush()

    doc_a = Document(
        organization_id=org_a.id,
        name="Doc A Secret Financials",
        original_filename="doc_a.pdf",
        mime_type="application/pdf",
        file_size=1024,
        storage_key=f"org_{org_a.id}/doc_a.pdf",
    )
    session.add(doc_a)

    # Create Organization B and Document B
    org_b = Organization(name=f"Tenant B {suffix}", slug=f"tenant-b-{suffix}")
    session.add(org_b)
    await session.flush()

    doc_b = Document(
        organization_id=org_b.id,
        name="Doc B Internal Strategy",
        original_filename="doc_b.pdf",
        mime_type="application/pdf",
        file_size=2048,
        storage_key=f"org_{org_b.id}/doc_b.pdf",
    )
    session.add(doc_b)
    await session.flush()

    # Query scoped strictly to Tenant A
    stmt_a = select(Document).where(Document.organization_id == org_a.id)
    tenant_a_docs = (await session.execute(stmt_a)).scalars().all()
    assert len(tenant_a_docs) == 1
    assert tenant_a_docs[0].name == "Doc A Secret Financials"
    assert tenant_a_docs[0].id == doc_a.id

    # Query scoped strictly to Tenant B
    stmt_b = select(Document).where(Document.organization_id == org_b.id)
    tenant_b_docs = (await session.execute(stmt_b)).scalars().all()
    assert len(tenant_b_docs) == 1
    assert tenant_b_docs[0].name == "Doc B Internal Strategy"
    assert tenant_b_docs[0].id == doc_b.id


@pytest.mark.asyncio
async def test_transaction_rollback(session: AsyncSession) -> None:
    """Verify session rollback discards uncommitted database mutations."""
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"Rollback Org {suffix}", slug=f"rollback-{suffix}")
    session.add(org)
    await session.flush()
    org_id = org.id

    # Roll back transaction explicitly
    await session.rollback()

    # Query database to confirm record does not exist
    stmt = select(Organization).where(Organization.id == org_id)
    result = (await session.execute(stmt)).scalar_one_or_none()
    assert result is None
