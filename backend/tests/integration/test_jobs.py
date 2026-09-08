"""Integration tests for background jobs and distributed worker architecture."""

import asyncio
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import create_access_token
from app.core.config import get_settings
from app.db.postgres import create_database_engine, create_session_factory
from app.jobs.cancellation import JobCancellationManager
from app.jobs.context import JobContext
from app.jobs.dispatcher import JobDispatcher
from app.jobs.exceptions import (
    JobCancellationError,
    JobIdempotencyConflictError,
    JobNotFoundError,
    RetryableJobError,
)
from app.jobs.models import Job
from app.jobs.queue import InMemoryJobQueue
from app.jobs.registry import TaskRegistry
from app.jobs.retry import RetryPolicy
from app.jobs.schemas import JobCreateRequest, JobPriority, JobStatus, JobType
from app.jobs.service import JobService
from app.jobs.tasks.chunking import ChunkingTask
from app.jobs.tasks.embeddings import EmbeddingTask
from app.jobs.tasks.ingestion import DocumentIngestionTask
from app.jobs.tasks.vector_indexing import VectorIndexingTask
from app.jobs.worker import Worker
from app.main import create_app
from app.models.organization import Organization
from app.models.role import OrganizationMember, Role
from app.models.user import User
from app.rbac.catalog import ROLE_ADMIN, ROLE_ANALYST, ROLE_VIEWER
from app.rbac.service import RBACService


@pytest.fixture
async def test_env() -> Any:
    """Set up real database engine and session factory for integration tests."""
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    app = create_app()
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield {
            "app": app,
            "client": client,
            "engine": engine,
            "session_factory": session_factory,
        }

    await engine.dispose()


async def setup_org_and_user(
    session: AsyncSession, role_name: str = ROLE_ADMIN
) -> tuple[Organization, User, str]:
    """Helper to seed org, user, role membership, and return access token."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    org = Organization(
        id=org_id,
        name=f"Jobs Org {org_id.hex[:6]}",
        slug=f"jobs-org-{org_id.hex[:6]}",
    )
    session.add(org)

    user = User(
        id=user_id,
        email=f"jobs_{user_id.hex[:8]}@example.com",
        first_name="Job",
        last_name="Tester",
        password_hash="test_hash",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    rbac_svc = RBACService()
    await rbac_svc.seed_system_rbac(session)
    role_res = await session.execute(select(Role).where(Role.name == role_name))
    role = role_res.scalar_one()

    membership = OrganizationMember(
        organization_id=org_id,
        user_id=user_id,
        role_id=role.id,
    )
    session.add(membership)
    await session.commit()

    token = create_access_token(
        user_id=user_id,
        extra_claims={"org_id": str(org_id), "role": role_name},
    )
    return org, user, token


class MockSuccessTask:
    """Simple successful task handler."""

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        context.report_progress(0.5, "Halfway done")
        return {"processed": True, "input_key": payload.get("key")}


class MockFailingTask:
    """Task handler that fails transiently or permanently depending on attempt."""

    def __init__(self, fail_until_attempt: int = 1) -> None:
        self.fail_until_attempt = fail_until_attempt

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        if context.attempt <= self.fail_until_attempt:
            raise RetryableJobError(f"Transient error on attempt {context.attempt}")
        return {"processed": True, "attempts": context.attempt}


class MockCancellableTask:
    """Task handler that checks cancellation checkpoints."""

    async def run(self, payload: dict[str, Any], context: JobContext) -> dict[str, Any]:
        if context.is_cancelled():
            raise JobCancellationError(context.job_id)
        # Simulate work
        await asyncio.sleep(0.05)
        if context.is_cancelled():
            raise JobCancellationError(context.job_id)
        return {"completed": True}


@pytest.mark.asyncio
async def test_job_dispatch_and_worker_execution_e2e(test_env: dict[str, Any]) -> None:
    """Test full pipeline: Dispatch -> DB persisted (queued) -> Worker poll -> Completed."""
    session_factory = test_env["session_factory"]
    queue = InMemoryJobQueue()
    registry = TaskRegistry()
    registry.register(JobType.CHUNKING.value, MockSuccessTask)

    dispatcher = JobDispatcher(queue)
    worker = Worker(
        queue=queue,
        session_factory=session_factory,
        registry=registry,
    )

    async with session_factory() as session:
        org, user, _ = await setup_org_and_user(session, ROLE_ADMIN)

        # Dispatch job
        job = await dispatcher.dispatch(
            db=session,
            organization_id=org.id,
            job_type=JobType.CHUNKING.value,
            payload={"key": "val123"},
            priority=JobPriority.HIGH.value,
            created_by=user.id,
        )

        assert job.status == JobStatus.QUEUED.value
        assert job.attempt == 0
        job_id = job.id

    # Worker processes one job
    processed = await worker.process_one(timeout=1.0)
    assert processed is True

    # Verify DB state
    async with session_factory() as session:
        stmt = select(Job).where(Job.id == job_id)
        updated_job = (await session.execute(stmt)).scalar_one()

        assert updated_job.status == JobStatus.COMPLETED.value
        assert updated_job.attempt == 1
        assert updated_job.result == {"processed": True, "input_key": "val123"}
        assert updated_job.progress == 1.0
        assert updated_job.started_at is not None
        assert updated_job.completed_at is not None


@pytest.mark.asyncio
async def test_job_idempotency_e2e(test_env: dict[str, Any]) -> None:
    """Verify deduplication with identical payload, and conflict with differing payload."""
    session_factory = test_env["session_factory"]
    queue = InMemoryJobQueue()
    dispatcher = JobDispatcher(queue)

    async with session_factory() as session:
        org, user, _ = await setup_org_and_user(session, ROLE_ADMIN)
        idempotency_key = f"idem-{uuid.uuid4().hex[:8]}"

        # First dispatch
        job1 = await dispatcher.dispatch(
            db=session,
            organization_id=org.id,
            job_type=JobType.EMBEDDING.value,
            payload={"document_id": "doc-1", "model": "text-embedding-3"},
            idempotency_key=idempotency_key,
            created_by=user.id,
        )

        # Second dispatch with SAME key and SAME payload: must return job1
        job2 = await dispatcher.dispatch(
            db=session,
            organization_id=org.id,
            job_type=JobType.EMBEDDING.value,
            payload={"document_id": "doc-1", "model": "text-embedding-3"},
            idempotency_key=idempotency_key,
            created_by=user.id,
        )
        assert job1.id == job2.id

        # Third dispatch with SAME key but DIFFERENT payload: must raise JobIdempotencyConflictError
        with pytest.raises(JobIdempotencyConflictError):
            await dispatcher.dispatch(
                db=session,
                organization_id=org.id,
                job_type=JobType.EMBEDDING.value,
                payload={"document_id": "doc-2", "model": "text-embedding-3"},
                idempotency_key=idempotency_key,
                created_by=user.id,
            )


@pytest.mark.asyncio
async def test_job_retry_and_recovery_e2e(test_env: dict[str, Any]) -> None:
    """Verify transient failure triggers retry_scheduled and eventual success."""
    session_factory = test_env["session_factory"]
    queue = InMemoryJobQueue()
    registry = TaskRegistry()
    failing_task = MockFailingTask(fail_until_attempt=1)
    registry.register(JobType.DOCUMENT_INGESTION.value, failing_task)

    # 0s delay retry policy for immediate retry in test
    policy = RetryPolicy(max_attempts=3, initial_delay=0.01, jitter=False)

    dispatcher = JobDispatcher(queue)
    worker = Worker(
        queue=queue,
        session_factory=session_factory,
        registry=registry,
        retry_policy=policy,
    )

    async with session_factory() as session:
        org, user, _ = await setup_org_and_user(session, ROLE_ADMIN)
        job = await dispatcher.dispatch(
            db=session,
            organization_id=org.id,
            job_type=JobType.DOCUMENT_INGESTION.value,
            payload={"test": 1},
            max_attempts=3,
        )
        job_id = job.id

    # Attempt 1: fails transiently
    await worker.process_one(timeout=1.0)

    async with session_factory() as session:
        stmt = select(Job).where(Job.id == job_id)
        j1 = (await session.execute(stmt)).scalar_one()
        assert j1.status == JobStatus.RETRY_SCHEDULED.value
        assert j1.attempt == 1
        assert "Transient error on attempt 1" in (j1.error_message or "")

    # Wait for delay to pass
    await asyncio.sleep(0.05)

    # Attempt 2: succeeds
    await worker.process_one(timeout=1.0)

    async with session_factory() as session:
        stmt = select(Job).where(Job.id == job_id)
        j2 = (await session.execute(stmt)).scalar_one()
        assert j2.status == JobStatus.COMPLETED.value
        assert j2.attempt == 2
        assert j2.result == {"processed": True, "attempts": 2}


@pytest.mark.asyncio
async def test_job_dead_letter_on_exhausted_attempts(test_env: dict[str, Any]) -> None:
    """Verify job transitions to DEAD_LETTER when maximum attempts are exhausted."""
    session_factory = test_env["session_factory"]
    queue = InMemoryJobQueue()
    registry = TaskRegistry()
    # Always fails
    registry.register(JobType.VECTOR_INDEXING.value, MockFailingTask(fail_until_attempt=99))

    policy = RetryPolicy(max_attempts=2, initial_delay=0.01, jitter=False)
    dispatcher = JobDispatcher(queue)
    worker = Worker(
        queue=queue,
        session_factory=session_factory,
        registry=registry,
        retry_policy=policy,
    )

    async with session_factory() as session:
        org, user, _ = await setup_org_and_user(session, ROLE_ADMIN)
        job = await dispatcher.dispatch(
            db=session,
            organization_id=org.id,
            job_type=JobType.VECTOR_INDEXING.value,
            payload={"doc": "vector"},
            max_attempts=2,
        )
        job_id = job.id

    # Attempt 1 -> retry_scheduled
    await worker.process_one(timeout=1.0)
    await asyncio.sleep(0.05)

    # Attempt 2 -> exhausts max_attempts (2) -> dead_letter
    await worker.process_one(timeout=1.0)

    async with session_factory() as session:
        stmt = select(Job).where(Job.id == job_id)
        dl_job = (await session.execute(stmt)).scalar_one()
        assert dl_job.status == JobStatus.DEAD_LETTER.value
        assert dl_job.attempt == 2
        assert dl_job.completed_at is not None


@pytest.mark.asyncio
async def test_worker_crash_and_visibility_recovery(test_env: dict[str, Any]) -> None:
    """Simulate worker crash before ACK: job visibility expires and another worker finishes it."""
    session_factory = test_env["session_factory"]
    # 0.1s visibility timeout
    queue = InMemoryJobQueue(visibility_timeout=0.1)
    registry = TaskRegistry()
    registry.register(JobType.EVALUATION.value, MockSuccessTask)

    dispatcher = JobDispatcher(queue)
    worker2 = Worker(queue=queue, session_factory=session_factory, registry=registry)

    async with session_factory() as session:
        org, user, _ = await setup_org_and_user(session, ROLE_ADMIN)
        job = await dispatcher.dispatch(
            db=session,
            organization_id=org.id,
            job_type=JobType.EVALUATION.value,
            payload={"eval": 1},
        )
        job_id = job.id

    # Worker 1 dequeues but crashes before ACK
    crashed_deq = await queue.dequeue("crashed-worker")
    assert crashed_deq == job_id

    # In-flight queue holds it
    depths = await queue.get_all_depths()
    assert depths["inflight"] == 1

    # Wait for visibility timeout to expire
    await asyncio.sleep(0.15)

    # Worker 2 picks up reclaimed job and completes it
    processed = await worker2.process_one(timeout=1.0)
    assert processed is True

    async with session_factory() as session:
        stmt = select(Job).where(Job.id == job_id)
        completed_job = (await session.execute(stmt)).scalar_one()
        assert completed_job.status == JobStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_job_cancellation_during_execution(test_env: dict[str, Any]) -> None:
    """Ensure cancellation request aborts job safely at checkpoint."""
    session_factory = test_env["session_factory"]
    queue = InMemoryJobQueue()
    registry = TaskRegistry()
    registry.register(JobType.REPORT_EXPORT.value, MockCancellableTask)

    dispatcher = JobDispatcher(queue)
    worker = Worker(queue=queue, session_factory=session_factory, registry=registry)

    async with session_factory() as session:
        org, user, _ = await setup_org_and_user(session, ROLE_ADMIN)
        job = await dispatcher.dispatch(
            db=session,
            organization_id=org.id,
            job_type=JobType.REPORT_EXPORT.value,
            payload={"report": "annual"},
        )
        job_id = job.id

        # Flag cancellation
        await JobCancellationManager.request_cancellation(session, job_id, org.id, "User aborted")

    # Worker processes: must abort and mark cancelled
    await worker.process_one(timeout=1.0)

    async with session_factory() as session:
        stmt = select(Job).where(Job.id == job_id)
        cancelled_job = (await session.execute(stmt)).scalar_one()
        assert cancelled_job.status == JobStatus.CANCELLED.value
        assert cancelled_job.cancelled_at is not None


@pytest.mark.asyncio
async def test_tenant_isolation_job_access(test_env: dict[str, Any]) -> None:
    """Org A creates a job; Org B must NOT be able to view, cancel, or retry it."""
    session_factory = test_env["session_factory"]
    service = JobService(queue=InMemoryJobQueue())

    async with session_factory() as session:
        org_a, _, _ = await setup_org_and_user(session, ROLE_ADMIN)
        org_b, _, _ = await setup_org_and_user(session, ROLE_ADMIN)

        job_req = JobCreateRequest(
            job_type=JobType.CHUNKING,
            payload={"doc": "orgA"},
        )
        job_a = await service.create_job(session, job_req, org_a.id)

        # Org B attempts to read Org A's job -> JobNotFoundError
        with pytest.raises(JobNotFoundError):
            await service.get_job(session, job_a.id, org_b.id)

        # Org B attempts to cancel Org A's job -> JobNotFoundError
        with pytest.raises(JobNotFoundError):
            await service.cancel_job(session, job_a.id, org_b.id)

        # Org B attempts to retry Org A's job -> JobNotFoundError
        with pytest.raises(JobNotFoundError):
            await service.retry_job(session, job_a.id, org_b.id)


@pytest.mark.asyncio
async def test_job_rbac_and_rest_api(test_env: dict[str, Any]) -> None:
    """Test REST API authorization: Viewer read-only, Analyst can create and cancel."""
    client: AsyncClient = test_env["client"]
    session_factory = test_env["session_factory"]

    async with session_factory() as session:
        org, user_viewer, viewer_token = await setup_org_and_user(session, ROLE_VIEWER)

        user_analyst_id = uuid.uuid4()
        user_analyst = User(
            id=user_analyst_id,
            email=f"analyst_{user_analyst_id.hex[:8]}@example.com",
            first_name="Analyst",
            last_name="Tester",
            password_hash="test_hash",
            is_active=True,
        )
        session.add(user_analyst)
        await session.flush()

        role_res = await session.execute(select(Role).where(Role.name == ROLE_ANALYST))
        role_analyst = role_res.scalar_one()

        session.add(
            OrganizationMember(
                organization_id=org.id,
                user_id=user_analyst_id,
                role_id=role_analyst.id,
            )
        )
        await session.commit()

        analyst_token = create_access_token(
            user_id=user_analyst_id,
            extra_claims={"org_id": str(org.id), "role": ROLE_ANALYST},
        )

    viewer_headers = {"Authorization": f"Bearer {viewer_token}", "X-Organization-ID": str(org.id)}
    analyst_headers = {"Authorization": f"Bearer {analyst_token}", "X-Organization-ID": str(org.id)}

    # 1. Viewer tries to enqueue job -> 403 Forbidden
    resp_viewer = await client.post(
        "/api/v1/jobs",
        json={"job_type": "chunking", "payload": {"doc": "v"}},
        headers=viewer_headers,
    )
    assert resp_viewer.status_code == 403

    # 2. Analyst enqueues job -> 202 Accepted
    resp_analyst = await client.post(
        "/api/v1/jobs",
        json={"job_type": "chunking", "payload": {"doc": "a"}},
        headers=analyst_headers,
    )
    assert resp_analyst.status_code == 202
    created_data = resp_analyst.json()
    job_id = created_data["job_id"]
    assert created_data["status"] == "queued"

    # 3. Viewer can READ job status -> 200 OK
    resp_get = await client.get(f"/api/v1/jobs/{job_id}", headers=viewer_headers)
    assert resp_get.status_code == 200
    assert resp_get.json()["job_id"] == job_id

    # 4. Viewer cannot CANCEL job -> 403 Forbidden
    resp_cancel_viewer = await client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        json={"reason": "try cancel"},
        headers=viewer_headers,
    )
    assert resp_cancel_viewer.status_code == 403

    # 5. Analyst can CANCEL job -> 200 OK
    resp_cancel_analyst = await client.post(
        f"/api/v1/jobs/{job_id}/cancel",
        json={"reason": "Analyst cancelled"},
        headers=analyst_headers,
    )
    assert resp_cancel_analyst.status_code == 200
    assert resp_cancel_analyst.json()["status"] == "cancelled"

    # 6. List jobs with pagination
    resp_list = await client.get("/api/v1/jobs?page=1&page_size=10", headers=analyst_headers)
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert list_data["total"] >= 1
    assert len(list_data["items"]) >= 1

    # 7. Health API
    resp_health = await client.get("/api/v1/jobs/health", headers=viewer_headers)
    assert resp_health.status_code == 200
    health_data = resp_health.json()
    assert "status" in health_data
    assert "queue_depths" in health_data


@pytest.mark.asyncio
async def test_task_adapters_execution() -> None:
    """Verify task adapter execution wraps underlying workers correctly."""
    context = JobContext(
        job_id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        job_type="document_ingestion",
        attempt=1,
        max_attempts=3,
    )

    # Ingestion adapter
    mock_ingestion_worker = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_count = 5
    mock_doc.title = "Test Paper"
    mock_ingestion_worker.process_document = AsyncMock(return_value=mock_doc)

    ingestion_task = DocumentIngestionTask(worker=mock_ingestion_worker)
    ingestion_res = await ingestion_task.run({"document_id": str(uuid.uuid4())}, context)
    assert ingestion_res["status"] == "completed"
    assert ingestion_res["page_count"] == 5

    # Chunking adapter
    mock_chunking_worker = MagicMock()
    mock_summary = MagicMock()
    mock_summary.total_chunks = 42
    mock_summary.avg_chunk_size = 250.0
    mock_chunking_worker.process_document = AsyncMock(return_value=mock_summary)

    chunking_task = ChunkingTask(worker=mock_chunking_worker)
    chunking_res = await chunking_task.run({"document_id": str(uuid.uuid4())}, context)
    assert chunking_res["status"] == "completed"
    assert chunking_res["chunks_created"] == 42

    # Embedding adapter
    mock_embedding_worker = MagicMock()
    mock_emb_summary = MagicMock()
    mock_emb_summary.embeddings_generated = 42
    mock_emb_summary.model_name = "bge-m3"
    mock_embedding_worker.process_document = AsyncMock(return_value=mock_emb_summary)

    embedding_task = EmbeddingTask(worker=mock_embedding_worker)
    emb_res = await embedding_task.run({"document_id": str(uuid.uuid4())}, context)
    assert emb_res["status"] == "completed"
    assert emb_res["embeddings_generated"] == 42

    # Vector indexing adapter
    mock_vector_worker = MagicMock()
    mock_vec_res = MagicMock()
    mock_vec_res.indexed_points = 42
    mock_vec_res.collection_name = "documents"
    mock_vector_worker.process_document = AsyncMock(return_value=mock_vec_res)

    vector_task = VectorIndexingTask(worker=mock_vector_worker)
    vec_res = await vector_task.run({"document_id": str(uuid.uuid4())}, context)
    assert vec_res["status"] == "completed"
    assert vec_res["indexed_points"] == 42
