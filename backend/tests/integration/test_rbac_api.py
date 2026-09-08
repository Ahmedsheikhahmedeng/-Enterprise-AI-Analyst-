"""Integration tests verifying RBAC authorization, role assignments, and permission enforcement."""

import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.auth.password import hash_password
from app.core.config import get_settings
from app.core.exceptions import ValidationAppException
from app.db.postgres import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
)
from app.main import create_app
from app.models.organization import Organization
from app.models.role import OrganizationMember, Permission, Role
from app.models.user import User
from app.rbac.catalog import (
    PERM_ANALYTICS_EXECUTE,
    PERM_AUDIT_READ,
    PERM_DOCUMENTS_DELETE,
    PERM_DOCUMENTS_READ,
    PERM_DOCUMENTS_WRITE,
    PERM_REPORTS_CREATE,
    PERM_USERS_MANAGE,
    ROLE_ADMIN,
    ROLE_ANALYST,
    ROLE_VIEWER,
    SYSTEM_PERMISSIONS,
)
from app.rbac.repository import RBACRepository
from app.rbac.service import RBACService


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provide AsyncClient wired to FastAPI app instance with PostgreSQL database state."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await dispose_database_engine(engine)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide real PostgreSQL session for DB state setup and verification."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session
    await dispose_database_engine(engine)


async def _create_test_organization(session: AsyncSession, name: str | None = None) -> Organization:
    """Helper to create a test organization."""
    uid = uuid.uuid4().hex[:8]
    org = Organization(
        name=name or f"Test Org {uid}",
        slug=f"test-org-{uid}",
        is_active=True,
    )
    session.add(org)
    await session.flush()
    return org


async def _create_test_user(session: AsyncSession, email: str | None = None) -> User:
    """Helper to create an active verified test user."""
    uid = uuid.uuid4().hex[:8]
    user = User(
        email=email or f"user_{uid}@example.com",
        password_hash=hash_password("Password123!"),
        first_name="Test",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_seeded(session: AsyncSession) -> None:
    """Ensure system roles and permissions are seeded."""
    service = RBACService()
    await service.seed_system_rbac(session)
    await session.flush()


@pytest.mark.asyncio
async def test_admin_role_authorization_matrix(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify user with Admin role is authorized for all administrative and operational actions."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    admin_user = await _create_test_user(db_session)

    # Lookup Admin role
    admin_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ADMIN, Role.organization_id.is_(None))
        )
    ).scalar_one()

    # Assign Admin role in org
    member = OrganizationMember(
        organization_id=org.id, user_id=admin_user.id, role_id=admin_role.id
    )
    db_session.add(member)
    await db_session.commit()

    token = create_access_token(user_id=admin_user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)}

    # Admin should access admin users endpoint (users.manage)
    r_admin = await async_client.get("/api/v1/admin/users", headers=headers)
    assert r_admin.status_code == 200
    assert r_admin.json()["message"] == "Admin user management access granted."

    # Admin should access read document endpoint (documents.read)
    r_doc = await async_client.get("/api/v1/rbac/test/read-document", headers=headers)
    assert r_doc.status_code == 200

    # Admin should access create report endpoint (reports.create)
    r_rep = await async_client.post("/api/v1/rbac/test/create-report", headers=headers)
    assert r_rep.status_code == 200

    # Verify service permissions directly
    service = RBACService()
    assert (
        await service.has_permission(db_session, admin_user.id, org.id, PERM_USERS_MANAGE) is True
    )
    assert (
        await service.has_permission(db_session, admin_user.id, org.id, PERM_DOCUMENTS_DELETE)
        is True
    )
    assert await service.has_permission(db_session, admin_user.id, org.id, PERM_AUDIT_READ) is True


@pytest.mark.asyncio
async def test_analyst_role_authorization_matrix(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify Analyst role grants reporting permissions but denies user/admin management."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    analyst_user = await _create_test_user(db_session)

    analyst_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ANALYST, Role.organization_id.is_(None))
        )
    ).scalar_one()

    member = OrganizationMember(
        organization_id=org.id, user_id=analyst_user.id, role_id=analyst_role.id
    )
    db_session.add(member)
    await db_session.commit()

    token = create_access_token(user_id=analyst_user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)}

    # Analyst must be denied access to admin users endpoint (403 Forbidden)
    r_admin = await async_client.get("/api/v1/admin/users", headers=headers)
    assert r_admin.status_code == 403
    err = r_admin.json()["error"]
    assert err["code"] == "FORBIDDEN"
    assert err["message"] == "You do not have permission to perform this action."

    # Analyst should access read document endpoint (200 OK)
    r_doc = await async_client.get("/api/v1/rbac/test/read-document", headers=headers)
    assert r_doc.status_code == 200

    # Analyst should access create report endpoint (200 OK)
    r_rep = await async_client.post("/api/v1/rbac/test/create-report", headers=headers)
    assert r_rep.status_code == 200

    # Verify service permissions directly
    service = RBACService()
    assert (
        await service.has_permission(db_session, analyst_user.id, org.id, PERM_DOCUMENTS_READ)
        is True
    )
    assert (
        await service.has_permission(db_session, analyst_user.id, org.id, PERM_DOCUMENTS_WRITE)
        is True
    )
    assert (
        await service.has_permission(db_session, analyst_user.id, org.id, PERM_ANALYTICS_EXECUTE)
        is True
    )
    assert (
        await service.has_permission(db_session, analyst_user.id, org.id, PERM_DOCUMENTS_DELETE)
        is False
    )
    assert (
        await service.has_permission(db_session, analyst_user.id, org.id, PERM_USERS_MANAGE)
        is False
    )


@pytest.mark.asyncio
async def test_viewer_role_authorization_matrix(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that Viewer role grants read-only access and denies writes and creation."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    viewer_user = await _create_test_user(db_session)

    viewer_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_VIEWER, Role.organization_id.is_(None))
        )
    ).scalar_one()

    member = OrganizationMember(
        organization_id=org.id, user_id=viewer_user.id, role_id=viewer_role.id
    )
    db_session.add(member)
    await db_session.commit()

    token = create_access_token(user_id=viewer_user.id)
    headers = {"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)}

    # Viewer must be denied admin endpoint (403)
    r_admin = await async_client.get("/api/v1/admin/users", headers=headers)
    assert r_admin.status_code == 403

    # Viewer must be allowed read document endpoint (200)
    r_doc = await async_client.get("/api/v1/rbac/test/read-document", headers=headers)
    assert r_doc.status_code == 200

    # Viewer must be denied report creation (403)
    r_rep = await async_client.post("/api/v1/rbac/test/create-report", headers=headers)
    assert r_rep.status_code == 403
    assert r_rep.json()["error"]["code"] == "FORBIDDEN"

    # Verify service permissions directly
    service = RBACService()
    assert (
        await service.has_permission(db_session, viewer_user.id, org.id, PERM_DOCUMENTS_READ)
        is True
    )
    assert (
        await service.has_permission(db_session, viewer_user.id, org.id, PERM_DOCUMENTS_WRITE)
        is False
    )
    assert (
        await service.has_permission(db_session, viewer_user.id, org.id, PERM_DOCUMENTS_DELETE)
        is False
    )
    assert (
        await service.has_permission(db_session, viewer_user.id, org.id, PERM_REPORTS_CREATE)
        is False
    )


@pytest.mark.asyncio
async def test_authentication_vs_authorization_status_codes(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify distinct 401 Unauthorized vs 403 Forbidden behavior."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)

    viewer_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_VIEWER, Role.organization_id.is_(None))
        )
    ).scalar_one()
    member = OrganizationMember(organization_id=org.id, user_id=user.id, role_id=viewer_role.id)
    db_session.add(member)
    await db_session.commit()

    endpoint = "/api/v1/rbac/test/create-report"
    headers_org = {"X-Organization-ID": str(org.id)}

    # 1. Missing authentication -> 401
    r_no_auth = await async_client.post(endpoint, headers=headers_org)
    assert r_no_auth.status_code == 401
    assert r_no_auth.json()["error"]["code"] == "MISSING_CREDENTIALS"

    # 2. Malformed / Invalid token -> 401
    r_bad_auth = await async_client.post(
        endpoint, headers={**headers_org, "Authorization": "Bearer not-a-valid-jwt"}
    )
    assert r_bad_auth.status_code == 401
    assert r_bad_auth.json()["error"]["code"] == "INVALID_TOKEN"

    # 3. Expired token -> 401
    expired_token = create_access_token(user_id=user.id, expires_delta=timedelta(seconds=-10))
    r_exp_auth = await async_client.post(
        endpoint, headers={**headers_org, "Authorization": f"Bearer {expired_token}"}
    )
    assert r_exp_auth.status_code == 401
    assert r_exp_auth.json()["error"]["code"] == "TOKEN_EXPIRED"

    # 4. Authenticated but missing permission -> 403
    valid_token = create_access_token(user_id=user.id)
    r_forbidden = await async_client.post(
        endpoint, headers={**headers_org, "Authorization": f"Bearer {valid_token}"}
    )
    assert r_forbidden.status_code == 403
    assert r_forbidden.json()["error"]["code"] == "FORBIDDEN"
    # Ensure permission internal name is not leaked in client response
    assert "reports.create" not in r_forbidden.json()["error"]["message"]


@pytest.mark.asyncio
async def test_multi_organization_user_context_isolation(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify permissions for a multi-org user are evaluated in the requested org context."""
    await _ensure_seeded(db_session)
    org_alpha = await _create_test_organization(db_session, name="Alpha Corp")
    org_beta = await _create_test_organization(db_session, name="Beta Corp")
    user = await _create_test_user(db_session)

    analyst_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ANALYST, Role.organization_id.is_(None))
        )
    ).scalar_one()
    viewer_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_VIEWER, Role.organization_id.is_(None))
        )
    ).scalar_one()

    # User is Analyst in Alpha, Viewer in Beta
    db_session.add(
        OrganizationMember(organization_id=org_alpha.id, user_id=user.id, role_id=analyst_role.id)
    )
    db_session.add(
        OrganizationMember(organization_id=org_beta.id, user_id=user.id, role_id=viewer_role.id)
    )
    await db_session.commit()

    token = create_access_token(user_id=user.id)

    # In Org Alpha (Analyst): reports.create is allowed (200)
    r_alpha = await async_client.post(
        "/api/v1/rbac/test/create-report",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_alpha.id)},
    )
    assert r_alpha.status_code == 200

    # In Org Beta (Viewer): reports.create is denied (403)
    r_beta = await async_client.post(
        "/api/v1/rbac/test/create-report",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org_beta.id)},
    )
    assert r_beta.status_code == 403

    # Without X-Organization-ID (ambiguous context with multiple memberships): must be denied (403)
    r_ambiguous = await async_client.post(
        "/api/v1/rbac/test/create-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_ambiguous.status_code == 403


@pytest.mark.asyncio
async def test_cross_organization_role_prevented(
    db_session: AsyncSession,
) -> None:
    """Verify that an organization cannot assign or utilize a role scoped to a different org."""
    await _ensure_seeded(db_session)
    org_a = await _create_test_organization(db_session, name="Tenant A")
    org_b = await _create_test_organization(db_session, name="Tenant B")
    user_a = await _create_test_user(db_session)

    # Create a custom role scoped strictly to Tenant B
    repo = RBACRepository()
    service = RBACService(repository=repo)
    role_b = await repo.create_role(
        db_session,
        name="TenantBCustomRole",
        description="Private to Tenant B",
        organization_id=org_b.id,
    )
    # Grant documents.manage to role_b
    perm_doc_manage = (
        await db_session.execute(select(Permission).where(Permission.name == "documents.manage"))
    ).scalar_one()
    await repo.assign_permission_to_role(
        db_session, role_id=role_b.id, permission_id=perm_doc_manage.id
    )
    await db_session.flush()

    # Attempt to assign Tenant B's role to a user in Tenant A must fail
    with pytest.raises(ValidationAppException) as exc_info:
        await service.assign_role(
            session=db_session,
            user_id=user_a.id,
            organization_id=org_a.id,
            role_id=role_b.id,
        )
    assert "belongs to organization" in str(exc_info.value.message)

    # Even if an invalid record were manually inserted, effective permissions should return empty
    invalid_member = OrganizationMember(
        organization_id=org_a.id, user_id=user_a.id, role_id=role_b.id
    )
    db_session.add(invalid_member)
    await db_session.flush()

    effective = await service.get_effective_permissions(
        db_session, user_id=user_a.id, organization_id=org_a.id
    )
    assert len(effective) == 0
    assert "documents.manage" not in effective


@pytest.mark.asyncio
async def test_dynamic_role_mutation_updates_permissions_immediately(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify that changing a user's role immediately grants or revokes effective permissions."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)
    admin = await _create_test_user(db_session)

    admin_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ADMIN, Role.organization_id.is_(None))
        )
    ).scalar_one()
    analyst_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ANALYST, Role.organization_id.is_(None))
        )
    ).scalar_one()
    viewer_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_VIEWER, Role.organization_id.is_(None))
        )
    ).scalar_one()

    # Admin membership
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=admin.id, role_id=admin_role.id)
    )
    # User starts as Viewer
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role_id=viewer_role.id)
    )
    await db_session.commit()

    user_token = create_access_token(user_id=user.id)
    admin_token = create_access_token(user_id=admin.id)
    user_headers = {"Authorization": f"Bearer {user_token}", "X-Organization-ID": str(org.id)}
    admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-ID": str(org.id)}

    # 1. As Viewer: reports.create is denied (403)
    r_v = await async_client.post("/api/v1/rbac/test/create-report", headers=user_headers)
    assert r_v.status_code == 403

    # 2. Admin promotes user to Analyst
    r_promote = await async_client.post(
        "/api/v1/rbac/roles/assign",
        headers=admin_headers,
        json={
            "user_id": str(user.id),
            "role_id": str(analyst_role.id),
            "organization_id": str(org.id),
        },
    )
    assert r_promote.status_code == 200

    # 3. Immediately as Analyst: reports.create is allowed (200)
    r_a = await async_client.post("/api/v1/rbac/test/create-report", headers=user_headers)
    assert r_a.status_code == 200

    # 4. Admin demotes user back to Viewer
    r_demote = await async_client.post(
        "/api/v1/rbac/roles/assign",
        headers=admin_headers,
        json={
            "user_id": str(user.id),
            "role_id": str(viewer_role.id),
            "organization_id": str(org.id),
        },
    )
    assert r_demote.status_code == 200

    # 5. Immediately: reports.create is again denied (403)
    r_v2 = await async_client.post("/api/v1/rbac/test/create-report", headers=user_headers)
    assert r_v2.status_code == 403

    # 6. Admin removes user from organization
    r_remove = await async_client.post(
        "/api/v1/rbac/roles/remove",
        headers=admin_headers,
        json={"user_id": str(user.id), "organization_id": str(org.id)},
    )
    assert r_remove.status_code == 200

    # 7. Immediately: user has no membership, document read is denied (403)
    r_read = await async_client.get("/api/v1/rbac/test/read-document", headers=user_headers)
    assert r_read.status_code == 403


@pytest.mark.asyncio
async def test_dynamic_permission_mutation_updates_role(
    db_session: AsyncSession,
) -> None:
    """Verify adding/removing permission to/from a role updates permissions immediately."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)

    repo = RBACRepository()
    service = RBACService(repository=repo)

    # Create a test role with no permissions initially
    role = await repo.create_role(db_session, name="DynamicRole", organization_id=org.id)
    await repo.assign_role_to_member(
        db_session, user_id=user.id, organization_id=org.id, role_id=role.id
    )
    await db_session.flush()

    # User has 0 permissions
    perms_initial = await service.get_effective_permissions(
        db_session, user_id=user.id, organization_id=org.id
    )
    assert len(perms_initial) == 0

    # Add documents.read to the role
    perm_read = (
        await db_session.execute(select(Permission).where(Permission.name == PERM_DOCUMENTS_READ))
    ).scalar_one()
    await repo.assign_permission_to_role(db_session, role_id=role.id, permission_id=perm_read.id)
    await db_session.flush()

    # User immediately has documents.read
    perms_after_add = await service.get_effective_permissions(
        db_session, user_id=user.id, organization_id=org.id
    )
    assert PERM_DOCUMENTS_READ in perms_after_add

    # Remove documents.read from the role
    await repo.remove_permission_from_role(db_session, role_id=role.id, permission_id=perm_read.id)
    await db_session.flush()

    # User immediately loses documents.read
    perms_after_remove = await service.get_effective_permissions(
        db_session, user_id=user.id, organization_id=org.id
    )
    assert PERM_DOCUMENTS_READ not in perms_after_remove


@pytest.mark.asyncio
async def test_single_query_effective_permissions_no_n_plus_one(
    db_session: AsyncSession,
) -> None:
    """Verify get_effective_user_permissions executes in a single query without N+1 loops."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)

    admin_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ADMIN, Role.organization_id.is_(None))
        )
    ).scalar_one()
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role_id=admin_role.id)
    )
    await db_session.commit()

    repo = RBACRepository()
    # Execute query
    permissions = await repo.get_effective_user_permissions(
        db_session, user_id=user.id, organization_id=org.id
    )
    # Admin has all system permissions returned at once
    assert len(permissions) == len(SYSTEM_PERMISSIONS)


@pytest.mark.asyncio
async def test_my_effective_permissions_endpoint(
    async_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Verify the /api/v1/rbac/permissions endpoint returns sorted permissions and role info."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)

    analyst_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ANALYST, Role.organization_id.is_(None))
        )
    ).scalar_one()
    db_session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role_id=analyst_role.id)
    )
    await db_session.commit()

    token = create_access_token(user_id=user.id)
    resp = await async_client.get(
        "/api/v1/rbac/permissions",
        headers={"Authorization": f"Bearer {token}", "X-Organization-ID": str(org.id)},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == str(user.id)
    assert data["organization_id"] == str(org.id)
    assert data["role_name"] == ROLE_ANALYST
    assert "reports.create" in data["permissions"]
    assert "users.manage" not in data["permissions"]


@pytest.mark.asyncio
async def test_duplicate_membership_constraint_and_clean_update(
    db_session: AsyncSession,
) -> None:
    """Verify assigning a role updates an existing membership rather than duplicating records."""
    await _ensure_seeded(db_session)
    org = await _create_test_organization(db_session)
    user = await _create_test_user(db_session)

    viewer_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_VIEWER, Role.organization_id.is_(None))
        )
    ).scalar_one()
    analyst_role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_ANALYST, Role.organization_id.is_(None))
        )
    ).scalar_one()

    repo = RBACRepository()
    # First assignment
    m1 = await repo.assign_role_to_member(
        db_session, user_id=user.id, organization_id=org.id, role_id=viewer_role.id
    )
    await db_session.flush()

    # Second assignment: should update the same record
    m2 = await repo.assign_role_to_member(
        db_session, user_id=user.id, organization_id=org.id, role_id=analyst_role.id
    )
    await db_session.flush()

    assert m1.id == m2.id
    assert m2.role_id == analyst_role.id

    # Check database count: exactly 1 membership
    members = (
        (
            await db_session.execute(
                select(OrganizationMember).where(
                    OrganizationMember.user_id == user.id,
                    OrganizationMember.organization_id == org.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(members) == 1


@pytest.mark.asyncio
async def test_duplicate_role_permission_idempotent_handling(
    db_session: AsyncSession,
) -> None:
    """Verify assigning existing permission to a role is idempotent without key violation."""
    await _ensure_seeded(db_session)
    repo = RBACRepository()

    role = (
        await db_session.execute(
            select(Role).where(Role.name == ROLE_VIEWER, Role.organization_id.is_(None))
        )
    ).scalar_one()
    perm = (
        await db_session.execute(select(Permission).where(Permission.name == PERM_DOCUMENTS_READ))
    ).scalar_one()

    # First assignment (already exists via seed)
    assoc1 = await repo.assign_permission_to_role(
        db_session, role_id=role.id, permission_id=perm.id
    )
    # Second assignment call
    assoc2 = await repo.assign_permission_to_role(
        db_session, role_id=role.id, permission_id=perm.id
    )
    assert assoc1.permission_id == assoc2.permission_id
