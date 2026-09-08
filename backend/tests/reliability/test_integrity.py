"""Unit tests verifying data integrity and checkpoint consistency post-failure."""

from app.reliability.assertions import ReliabilityAssertionEngine
from app.reliability.enums import AssertionStatus


def test_data_integrity_clean_checkpoints() -> None:
    """Verify zero corrupted rows and consistent checkpoints."""
    res = ReliabilityAssertionEngine.assert_data_integrity(
        corrupted_records=0,
        orphaned_chunks=0,
        checkpoint_consistent=True,
    )
    assert res.status == AssertionStatus.PASSED
    assert res.is_passed is True


def test_data_integrity_corruption_detected() -> None:
    """Verify corrupted records or orphaned chunks cause assertion failure."""
    res = ReliabilityAssertionEngine.assert_data_integrity(
        corrupted_records=3,
        orphaned_chunks=10,
        checkpoint_consistent=False,
    )
    assert res.status == AssertionStatus.FAILED
    assert res.is_passed is False
