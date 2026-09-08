"""Unit tests for Continuous Evaluation REST API endpoints."""

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.continuous_evaluation.api.routes as routes_module
from app.continuous_evaluation.api.routes import router
from app.continuous_evaluation.application.benchmark_service import BenchmarkService
from app.continuous_evaluation.application.calibration_service import CalibrationService
from app.continuous_evaluation.application.comparison_service import ComparisonService
from app.continuous_evaluation.application.evaluation_service import ContinuousEvaluationService
from app.continuous_evaluation.application.monitoring_service import MonitoringService
from app.continuous_evaluation.application.quality_gate_service import QualityGateService
from app.continuous_evaluation.application.regression_service import RegressionService
from app.continuous_evaluation.application.release_service import ReleaseQualityPolicy
from app.db.postgres import get_db_session
from app.tenancy.context import TenantContext
from tests.unit.test_continuous_evaluation import MockContinuousEvaluationRepository


@pytest.fixture
def test_setup() -> tuple[TestClient, uuid.UUID, MockContinuousEvaluationRepository]:
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    repo = MockContinuousEvaluationRepository()

    app = FastAPI()
    app.include_router(router)

    # Mock DB session
    mock_session = AsyncMock()
    app.dependency_overrides[get_db_session] = lambda: mock_session

    from app.tenancy.dependencies import get_current_tenant

    app.dependency_overrides[get_current_tenant] = lambda: TenantContext(
        organization_id=org_id,
        user_id=user_id,
        membership_id=uuid.uuid4(),
        role_id=uuid.uuid4(),
        role_name="admin",
        permissions=frozenset(
            {
                "evaluation.monitor.read",
                "evaluation.benchmark.manage",
                "evaluation.run.execute",
                "evaluation.quality_gate.read",
                "evaluation.release.approve",
                "evaluation.human_review",
            }
        ),
    )

    from app.continuous_evaluation.api.routes import EvaluationServices

    routes_module._get_services = lambda db: EvaluationServices(
        repo=repo,
        benchmark=BenchmarkService(repo),
        evaluation=ContinuousEvaluationService(repo),
        regression=RegressionService(repo),
        gate=QualityGateService(repo),
        calibration=CalibrationService(repo),
        comparison=ComparisonService(repo),
        monitoring=MonitoringService(repo),
        release=ReleaseQualityPolicy(),
    )

    client = TestClient(app)
    return client, org_id, repo


def test_benchmark_api_endpoints(
    test_setup: tuple[TestClient, uuid.UUID, MockContinuousEvaluationRepository],
) -> None:
    client, org_id, repo = test_setup
    dataset_id = str(uuid.uuid4())

    # 1. Create benchmark
    create_payload = {
        "name": "API Test Benchmark",
        "task_type": "RAG",
        "target": "RAG",
        "dataset_id": dataset_id,
        "version": 1,
    }
    res = client.post("/evaluation/benchmarks", json=create_payload)
    assert res.status_code == 201
    b_data = res.json()
    b_id = b_data["id"]
    assert b_data["name"] == "API Test Benchmark"

    # 2. List benchmarks
    res = client.get("/evaluation/benchmarks")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # 3. Get benchmark
    res = client.get(f"/evaluation/benchmarks/{b_id}")
    assert res.status_code == 200
    assert res.json()["id"] == b_id

    # 4. Set baseline
    baseline_run_id = str(uuid.uuid4())
    res = client.post(
        f"/evaluation/benchmarks/{b_id}/baseline", json={"baseline_run_id": baseline_run_id}
    )
    assert res.status_code == 200
    assert res.json()["baseline_run_id"] == baseline_run_id


def test_quality_gate_api_endpoints(
    test_setup: tuple[TestClient, uuid.UUID, MockContinuousEvaluationRepository],
) -> None:
    client, org_id, repo = test_setup

    # Create gate
    gate_payload = {
        "name": "API Quality Gate",
        "description": "Gate for testing",
        "rules": [
            {"metric_name": "groundedness", "min_threshold": 0.90, "is_critical": True},
        ],
    }
    res = client.post("/evaluation/quality-gates", json=gate_payload)
    assert res.status_code == 201
    gate_id = res.json()["gate_id"]

    # List gates
    res = client.get("/evaluation/quality-gates")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Evaluate gate
    eval_payload = {
        "gate_id": gate_id,
        "run_id": str(uuid.uuid4()),
        "scorecard": {"metrics": {"groundedness": 0.95}},
    }
    res = client.post("/evaluation/quality-gates/evaluate", json=eval_payload)
    assert res.status_code == 200
    assert res.json()["decision"] == "PASS"


def test_comparison_and_monitoring_api(
    test_setup: tuple[TestClient, uuid.UUID, MockContinuousEvaluationRepository],
) -> None:
    client, org_id, repo = test_setup

    # Comparison endpoint
    compare_payload = {
        "comparison_type": "MODEL",
        "baseline_id": "model_v1",
        "candidate_id": "model_v2",
        "baseline_scorecard": {"segmented_scores": {"quality_score": 0.80}},
        "candidate_scorecard": {"segmented_scores": {"quality_score": 0.90}},
    }
    res = client.post("/evaluation/compare", json=compare_payload)
    assert res.status_code == 200
    assert res.json()["winner"] == "model_v2"

    # Production quality sampling
    prod_payload = {
        "query": "Hello contact me at test@company.com",
        "response": "Here is the response",
        "sampling_strategy": "RANDOM",
        "retention_days": 30,
    }
    res = client.post("/evaluation/production-quality", json=prod_payload)
    assert res.status_code == 201
    assert res.json()["redacted"] is True
    assert "[REDACTED_EMAIL]" in res.json()["query"]

    # List production samples
    res = client.get("/evaluation/production-quality")
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Human review
    human_payload = {
        "evaluator_id": str(uuid.uuid4()),
        "accuracy_score": 4.5,
        "helpfulness_score": 4.0,
        "grounding_score": 5.0,
        "clarity_score": 4.5,
        "comments": "High quality answer",
    }
    res = client.post("/evaluation/human-evaluation", json=human_payload)
    assert res.status_code == 201
    assert res.json()["normalized_score"] > 0.80
