"""Unit tests verifying mathematical consistency between injected error rates and SRE SLO/burn rate."""

import uuid

from app.sre.burn_rate import calculate_single_burn_rate
from app.sre.enums import ReleaseGateDecisionEnum, SLOStatusEnum
from app.sre.gates import evaluate_release_safety
from app.sre.sli import compute_availability, compute_error_rate
from app.sre.slo import evaluate_slo_compliance


def test_injected_error_rate_mathematical_consistency() -> None:
    """Verify that a 10% injected failure rate reflects exactly in SLI, SLO, and Error Budget."""
    # 1. SLI Calculation
    total_reqs = 1000
    failed_reqs = 100  # 10% error spike injected
    successful_reqs = total_reqs - failed_reqs

    sli_avail = compute_availability(successful_reqs, total_reqs)
    sli_err = compute_error_rate(failed_reqs, total_reqs)
    assert sli_avail == 0.90
    assert sli_err == 0.10

    # 2. SLO Target Evaluation (Target: 99.9% availability => allowed error rate = 0.001)
    target = 0.999
    compliance = evaluate_slo_compliance(
        slo_id=uuid.uuid4(),
        name="API Availability",
        service="api",
        target_value=target,
        window_seconds=3600,
        actual_value=sli_avail,
    )
    assert compliance.status == SLOStatusEnum.BREACHED
    assert compliance.error_budget.budget_remaining_percent == 0.0

    # 3. Burn Rate Calculation (actual error rate 0.10 / allowed error rate 0.001 = 100x burn rate)
    burn_rate = calculate_single_burn_rate(actual_error_rate=sli_err, allowed_error_rate=0.001)
    assert burn_rate == 100.0
    assert burn_rate > 14.4  # Fast burn threshold

    # 4. Release Safety Gate should BLOCK release
    gate_decision, reasons = evaluate_release_safety(
        service="api",
        open_incidents=[{"severity": "SEV1", "status": "OPEN"}],
        error_budget_remaining_pct=0.0,
        recent_error_rate=sli_err,
    )
    assert gate_decision == ReleaseGateDecisionEnum.BLOCK
    assert len(reasons) >= 1
