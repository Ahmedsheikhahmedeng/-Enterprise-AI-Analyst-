"""Unit tests for Data Classification levels and sensitivity policy defaults."""

from app.compliance.classification import DataClassificationEngine
from app.compliance.enums import DataClassificationLevel


def test_default_policies_exist_for_all_tiers() -> None:
    for tier in DataClassificationLevel:
        policy = DataClassificationEngine.get_effective_policy(tier.value)
        assert "allowed_providers" in policy
        assert "allow_external_processing" in policy
        assert "retention_days" in policy


def test_restricted_tier_disallows_external_processing() -> None:
    policy = DataClassificationEngine.get_effective_policy(DataClassificationLevel.RESTRICTED.value)
    assert policy["allow_external_processing"] is False
    assert policy["allow_export"] is False


def test_custom_tenant_policy_override() -> None:
    override = {"allow_export": True, "retention_days": 45}
    policy = DataClassificationEngine.get_effective_policy(
        DataClassificationLevel.RESTRICTED.value, custom_tenant_policy=override
    )
    assert policy["allow_export"] is True
    assert policy["retention_days"] == 45
    # Non-overridden values remain
    assert policy["allow_external_processing"] is False
