"""Unit tests verifying dependency degradation and health matrix responses."""

import pytest

from app.sre.dependencies import check_all_dependencies
from app.sre.enums import DependencyHealthStatusEnum


@pytest.mark.asyncio
async def test_dependency_matrix_health_check() -> None:
    """Verify check_all_dependencies returns healthy status when all dependencies are simulated healthy."""
    res = await check_all_dependencies()
    assert res.overall_status == DependencyHealthStatusEnum.HEALTHY
    assert len(res.dependencies) >= 5
    assert len(res.degraded_components) == 0


def test_dependency_status_enum_values() -> None:
    """Verify valid dependency health status enums."""
    assert DependencyHealthStatusEnum.HEALTHY == "HEALTHY"
    assert DependencyHealthStatusEnum.DEGRADED == "DEGRADED"
    assert DependencyHealthStatusEnum.UNHEALTHY == "UNHEALTHY"
    assert DependencyHealthStatusEnum.UNKNOWN == "UNKNOWN"
