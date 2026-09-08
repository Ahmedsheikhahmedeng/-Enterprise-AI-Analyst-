"""Unit tests for agent tool execution governance across data classifications."""

from app.compliance.classification import DataClassificationEngine
from app.compliance.enums import DataClassificationLevel


def test_agent_execution_allowed_on_internal_data() -> None:
    verdict = DataClassificationEngine.evaluate_agent_governance(
        classification=DataClassificationLevel.INTERNAL.value,
        tool_name="sql_generator",
        is_external_tool=False,
    )
    assert verdict.allowed is True
    assert verdict.verdict == "ALLOW"


def test_agent_execution_blocked_on_restricted_data() -> None:
    verdict = DataClassificationEngine.evaluate_agent_governance(
        classification=DataClassificationLevel.RESTRICTED.value,
        tool_name="sql_generator",
        is_external_tool=False,
    )
    assert verdict.allowed is False
    assert verdict.verdict == "BLOCK"
    assert "Autonomous agent execution blocked" in verdict.reason


def test_external_tool_blocked_on_confidential_if_not_approved() -> None:
    override = {"allow_external_processing": False}
    verdict = DataClassificationEngine.evaluate_agent_governance(
        classification=DataClassificationLevel.CONFIDENTIAL.value,
        tool_name="web_search",
        is_external_tool=True,
        custom_tenant_policy=override,
    )
    assert verdict.allowed is False
    assert verdict.verdict == "BLOCK"
