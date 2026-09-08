"""Unit tests for LLM provider routing governance against data classifications."""

from app.compliance.classification import DataClassificationEngine
from app.compliance.enums import DataClassificationLevel


def test_public_data_routes_to_external_provider() -> None:
    verdict = DataClassificationEngine.evaluate_llm_routing(
        classification=DataClassificationLevel.PUBLIC.value,
        provider="openai",
    )
    assert verdict.allowed is True
    assert verdict.verdict == "ALLOW"


def test_restricted_data_blocks_external_provider() -> None:
    verdict = DataClassificationEngine.evaluate_llm_routing(
        classification=DataClassificationLevel.RESTRICTED.value,
        provider="openai",
    )
    assert verdict.allowed is False
    assert verdict.verdict == "BLOCK"
    assert "External processing prohibited" in verdict.reason


def test_restricted_data_allows_local_provider() -> None:
    verdict = DataClassificationEngine.evaluate_llm_routing(
        classification=DataClassificationLevel.RESTRICTED.value,
        provider="local",
    )
    assert verdict.allowed is True
    assert verdict.verdict == "ALLOW"
