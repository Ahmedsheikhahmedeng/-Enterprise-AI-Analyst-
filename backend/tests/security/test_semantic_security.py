"""Security and isolation tests for Semantic Catalog and Semantic Layer."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.semantic.application.mapping_service import MappingService
from app.semantic.application.metric_compiler import MetricCompiler
from app.semantic.domain.errors import InvalidMetricFormulaError, SemanticError
from app.semantic.infrastructure.repository import SemanticRepository


@pytest.mark.asyncio
async def test_cross_tenant_business_term_isolation() -> None:
    """Verify Tenant A cannot access or update Tenant B's business terms."""
    org_b = uuid.uuid4()
    term_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    # Mock query returning None when scoped to Org B
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    repo = SemanticRepository(mock_session)
    term = await repo.get_term(term_id, organization_id=org_b)
    assert term is None


@pytest.mark.asyncio
async def test_cross_tenant_mapping_prevention() -> None:
    """Verify creating a semantic mapping against another tenant's dataset is rejected."""
    org_a = uuid.uuid4()
    foreign_dataset_id = uuid.uuid4()
    column_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    # Dataset not found for Tenant A
    mock_result.scalars.return_value.first.return_value = None
    mock_session.execute.return_value = mock_result

    mapping_svc = MappingService(mock_session)

    with pytest.raises(SemanticError, match="Target Dataset .* not found"):
        await mapping_svc.create_mapping(
            organization_id=org_a,
            semantic_object_type="metric",
            semantic_object_id=uuid.uuid4(),
            dataset_id=foreign_dataset_id,
            column_id=column_id,
        )


def test_metric_formula_injection_vectors() -> None:
    """Verify various SQL injection vectors are caught and rejected by MetricCompiler."""
    attack_vectors = [
        "SUM(val); SHUTDOWN;",
        "AVG(val) UNION SELECT password FROM users",
        "SUM(val) /* comment bypass */",
        "COUNT(val) -- line comment",
        "EXEC xp_cmdshell('dir')",
        "SUM(val) INTO OUTFILE '/tmp/hack'",
    ]
    for vector in attack_vectors:
        with pytest.raises(InvalidMetricFormulaError):
            MetricCompiler.validate_formula(vector)
