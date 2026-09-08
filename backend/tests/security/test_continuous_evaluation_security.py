"""Security tests for continuous evaluation tenant isolation, PII scrubbing, and RBAC release approval."""

import uuid

import pytest

from app.continuous_evaluation.application.benchmark_service import BenchmarkService
from app.continuous_evaluation.application.monitoring_service import MonitoringService
from app.continuous_evaluation.application.quality_gate_service import QualityGateService
from app.continuous_evaluation.application.release_service import ReleaseQualityPolicy
from app.continuous_evaluation.domain.enums import EvaluationTarget
from app.continuous_evaluation.domain.errors import (
    BenchmarkNotFoundError,
    QualityGateNotFoundError,
    ReleaseBlockedError,
)
from app.continuous_evaluation.domain.models import QualityGateRule
from tests.unit.test_continuous_evaluation import MockContinuousEvaluationRepository


@pytest.mark.asyncio
async def test_tenant_isolation_benchmark_leakage() -> None:
    """Tenant A benchmark must be strictly invisible and inaccessible to Tenant B."""
    repo = MockContinuousEvaluationRepository()
    service = BenchmarkService(repo)

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    benchmark_a = await service.create_benchmark(
        organization_id=tenant_a,
        name="Confidential Tenant A Benchmark",
        task_type="SQL",
        target=EvaluationTarget.SQL,
        dataset_id=uuid.uuid4(),
    )

    # Tenant A accesses it successfully
    res_a = await service.get_benchmark(benchmark_a.id, tenant_a)
    assert res_a.name == "Confidential Tenant A Benchmark"

    # Tenant B attempt raises BenchmarkNotFoundError
    with pytest.raises(BenchmarkNotFoundError):
        await service.get_benchmark(benchmark_a.id, tenant_b)

    # Listing benchmarks for Tenant B returns 0 items
    list_b = await service.list_benchmarks(tenant_b)
    assert len(list_b) == 0


@pytest.mark.asyncio
async def test_tenant_isolation_quality_gate_leakage() -> None:
    """Tenant A quality gate must be invisible and inaccessible to Tenant B."""
    repo = MockContinuousEvaluationRepository()
    service = QualityGateService(repo)

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    gate_a = await service.create_gate(
        organization_id=tenant_a,
        name="Tenant A Production Gate",
        rules=[QualityGateRule(metric_name="sql_accuracy", min_threshold=0.99)],
    )

    # Tenant B attempt to read Tenant A's gate raises QualityGateNotFoundError
    with pytest.raises(QualityGateNotFoundError):
        await service.get_gate(gate_a, tenant_b)


@pytest.mark.asyncio
async def test_pii_and_secret_redaction_before_persistence() -> None:
    """Ensure sensitive credentials and tokens are scrubbed prior to storage."""
    repo = MockContinuousEvaluationRepository()
    service = MonitoringService(repo)
    tenant_id = uuid.uuid4()

    malicious_query = "SELECT * FROM users WHERE email='ceo@enterprise.com' AND api_key='sk-prod-super-secret-key-123456789'"
    sample = await service.capture_production_sample(
        organization_id=tenant_id,
        query=malicious_query,
        response="Retrieved user details",
    )

    assert sample.redacted is True
    assert "ceo@enterprise.com" not in sample.query
    assert "sk-prod-super-secret-key-123456789" not in sample.query
    assert "[REDACTED_EMAIL]" in sample.query
    assert "[REDACTED_SECRET]" in sample.query


def test_agent_release_approval_strictly_blocked() -> None:
    """Autonomous agent must never be permitted to approve releases."""
    policy = ReleaseQualityPolicy()

    # Autonomous agent attempt must raise ReleaseBlockedError
    with pytest.raises(
        ReleaseBlockedError, match="Autonomous agents cannot approve release decisions"
    ):
        policy.enforce_release([], approver_is_agent=True)
