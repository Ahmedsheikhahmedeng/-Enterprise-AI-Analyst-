"""Unit tests verifying the Chaos Scenario Catalog and Registry integrity."""

from app.reliability.enums import FaultType, ScenarioCategory
from app.reliability.scenarios import (
    BUILTIN_SCENARIOS,
    GLOBAL_SCENARIO_REGISTRY,
    ScenarioDefinition,
    ScenarioRegistry,
)


def test_scenario_catalog_completeness() -> None:
    """Verify that all 22 minimum required scenarios exist and are registered."""
    assert len(BUILTIN_SCENARIOS) >= 22
    all_registered = GLOBAL_SCENARIO_REGISTRY.list_all()
    assert len(all_registered) >= 22

    # Verify presence of the specific 22 scenarios
    expected_scenario_ids = {
        "scen-pg-outage",
        "scen-pg-latency",
        "scen-redis-outage",
        "scen-redis-latency",
        "scen-qdrant-outage",
        "scen-qdrant-latency",
        "scen-llm-timeout",
        "scen-llm-5xx",
        "scen-llm-429",
        "scen-llm-malformed",
        "scen-llm-failover",
        "scen-worker-crash",
        "scen-queue-backlog",
        "scen-dlq-transition",
        "scen-sse-disconnect",
        "scen-sse-reconnect",
        "scen-api-latency",
        "scen-api-error-spike",
        "scen-partial-rag",
        "scen-tenant-isolation",
        "scen-dependency-recovery",
        "scen-release-gate-block",
    }
    actual_ids = {s.id for s in all_registered}
    assert expected_scenario_ids.issubset(actual_ids)


def test_scenario_attributes_and_bounds() -> None:
    """Verify each scenario adheres to strict boundary and timeout constraints."""
    for s in BUILTIN_SCENARIOS:
        assert isinstance(s.id, str) and s.id.startswith("scen-")
        assert len(s.name) >= 5
        assert len(s.description) >= 10
        assert isinstance(s.category, ScenarioCategory)
        assert s.severity in ("SEV1", "SEV2", "SEV3", "SEV4")
        assert isinstance(s.fault_type, FaultType)
        assert 5 <= s.timeout_seconds <= 600
        assert s.max_duration_seconds >= s.timeout_seconds
        assert len(s.preconditions) >= 1
        assert len(s.expected_outcomes) >= 1


def test_scenario_registry_filter_by_category() -> None:
    """Verify registry filtering by category."""
    registry = ScenarioRegistry()
    db_scenarios = registry.list_all(category=ScenarioCategory.DATABASE)
    assert len(db_scenarios) >= 2
    for s in db_scenarios:
        assert s.category == ScenarioCategory.DATABASE

    llm_scenarios = registry.list_all(category=ScenarioCategory.LLM)
    assert len(llm_scenarios) >= 5
    for s in llm_scenarios:
        assert s.category == ScenarioCategory.LLM


def test_custom_scenario_registration() -> None:
    """Verify dynamic registration of new custom scenarios."""
    registry = ScenarioRegistry()
    custom = ScenarioDefinition(
        id="scen-custom-disk-pressure",
        name="Disk Pressure Emulation",
        description="Simulate temporary volume filling to 95% capacity.",
        category=ScenarioCategory.RESOURCE,
        severity="SEV3",
        fault_type=FaultType.API_LATENCY,
        timeout_seconds=30,
        parameters={"disk_used_pct": 95},
        preconditions=["Host filesystem online"],
        expected_outcomes=["Warning alert logged"],
    )
    registry.register(custom)
    retrieved = registry.get("scen-custom-disk-pressure")
    assert retrieved is not None
    assert retrieved.name == "Disk Pressure Emulation"
