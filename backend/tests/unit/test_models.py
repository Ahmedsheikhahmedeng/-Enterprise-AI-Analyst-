import uuid

from app.models import (
    AnalysisRun,
    AuditLog,
    Base,
    Conversation,
    Dataset,
    DataSource,
    Document,
    DocumentChunk,
    LLMRequest,
    Organization,
    Report,
    UsageEvent,
    User,
)


def test_base_metadata_contains_all_19_tables() -> None:
    """Verify DeclarativeBase metadata has registered all 19 domain tables."""
    expected_tables = {
        "users",
        "organizations",
        "roles",
        "permissions",
        "role_permissions",
        "organization_members",
        "documents",
        "document_chunks",
        "datasets",
        "dataset_columns",
        "data_sources",
        "conversations",
        "messages",
        "analysis_runs",
        "analysis_steps",
        "reports",
        "audit_logs",
        "usage_events",
        "llm_requests",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables)


def test_user_model_attributes() -> None:
    """Verify User ORM model column definitions and defaults."""
    assert User.__table__.c.is_active.default.arg is True
    assert User.__table__.c.is_verified.default.arg is False

    user = User(
        email="test@example.com",
        password_hash="hashed_secret",
        first_name="Alice",
        last_name="Smith",
        is_active=True,
        is_verified=False,
    )
    assert user.email == "test@example.com"
    assert user.password_hash == "hashed_secret"
    assert user.first_name == "Alice"
    assert user.last_name == "Smith"
    assert user.is_active is True
    assert user.is_verified is False


def test_organization_model_attributes() -> None:
    """Verify Organization ORM model attributes and defaults."""
    assert Organization.__table__.c.is_active.default.arg is True

    org = Organization(
        name="Acme Corp",
        slug="acme-corp",
        is_active=True,
    )
    assert org.name == "Acme Corp"
    assert org.slug == "acme-corp"
    assert org.is_active is True


def test_tenant_scoped_models_have_organization_id() -> None:
    """Verify all tenant-owned models define an organization_id column."""
    tenant_models = [
        Document,
        DocumentChunk,
        Dataset,
        DataSource,
        Conversation,
        AnalysisRun,
        Report,
        AuditLog,
        UsageEvent,
        LLMRequest,
    ]
    for model in tenant_models:
        assert hasattr(model, "organization_id"), f"{model.__name__} must define organization_id"


def test_document_chunk_model_instantiation() -> None:
    """Verify DocumentChunk can be instantiated with structured metadata."""
    chunk = DocumentChunk(
        organization_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        content="Revenue grew by 15%",
        page_number=1,
        metadata_={"embedding_model": "text-embedding-3-small"},
    )
    assert chunk.chunk_index == 0
    assert chunk.content == "Revenue grew by 15%"
    assert chunk.metadata_ == {"embedding_model": "text-embedding-3-small"}
