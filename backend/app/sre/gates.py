"""Release safety gate evaluating automated deployment viability against live SRE health."""

from typing import Any

from app.sre.enums import IncidentSeverityEnum, ReleaseGateDecisionEnum


def evaluate_release_safety(
    service: str,
    open_incidents: list[dict[str, Any]],
    error_budget_remaining_pct: float | None,
    recent_error_rate: float | None,
    min_budget_remaining_pct: float = 10.0,
    max_error_rate: float = 0.05,
    critical_security_findings: int = 0,
    mandatory_control_failures: int = 0,
    tenant_isolation_failure: bool = False,
    audit_integrity_valid: bool = True,
    expired_critical_risk_acceptances: int = 0,
    critical_cost_anomalies: int = 0,
    budget_exhaustion_detected: bool = False,
    unknown_pricing_ratio: float = 0.0,
    max_unknown_pricing_ratio: float = 0.05,
    cost_attribution_failure: bool = False,
) -> tuple[ReleaseGateDecisionEnum, list[str]]:
    """Evaluate whether a release should be ALLOWED, WARNED, or BLOCKED.

    Policy:
    - BLOCK if any open SEV1 or SEV2 incident exists.
    - BLOCK if error budget remaining < min_budget_remaining_pct.
    - BLOCK if recent error rate > max_error_rate.
    - BLOCK if critical_security_findings > 0.
    - BLOCK if mandatory_control_failures > 0.
    - BLOCK if tenant_isolation_failure is True.
    - BLOCK if audit_integrity_valid is False.
    - BLOCK if expired_critical_risk_acceptances > 0.
    - BLOCK if critical_cost_anomalies > 0 (TASK 40 FinOps).
    - BLOCK if budget_exhaustion_detected is True (TASK 40 FinOps).
    - BLOCK if unknown_pricing_ratio > max_unknown_pricing_ratio (TASK 40 FinOps).
    - BLOCK if cost_attribution_failure is True (TASK 40 FinOps).
    - WARN if any open SEV3 incident exists or error budget is between min_budget and 2x min_budget.
    - ALLOW if all SRE, compliance security, and FinOps criteria pass.
    """
    reasons: list[str] = []
    is_blocked = False
    is_warned = False

    # 1. Compliance & Security Posture checks (TASK 39)
    if critical_security_findings > 0:
        is_blocked = True
        reasons.append(
            f"Blocked: {critical_security_findings} unresolved CRITICAL security finding(s)."
        )

    if mandatory_control_failures > 0:
        is_blocked = True
        reasons.append(
            f"Blocked: {mandatory_control_failures} mandatory compliance control(s) in FAIL state."
        )

    if tenant_isolation_failure:
        is_blocked = True
        reasons.append("Blocked: Tenant isolation barrier failure detected.")

    if not audit_integrity_valid:
        is_blocked = True
        reasons.append("Blocked: Audit log cryptographic hash chain validation failed.")

    if expired_critical_risk_acceptances > 0:
        is_blocked = True
        reasons.append(
            f"Blocked: {expired_critical_risk_acceptances} expired critical risk acceptance(s)."
        )

    # 2. Enterprise FinOps & Cost Governance checks (TASK 40)
    if critical_cost_anomalies > 0:
        is_blocked = True
        reasons.append(
            f"Blocked: {critical_cost_anomalies} unresolved CRITICAL FinOps cost anomaly/spike(s)."
        )

    if budget_exhaustion_detected:
        is_blocked = True
        reasons.append("Blocked: Organization or scoped FinOps financial budget is EXHAUSTED.")

    if unknown_pricing_ratio > max_unknown_pricing_ratio:
        is_blocked = True
        reasons.append(
            f"Blocked: Unknown pricing ratio ({unknown_pricing_ratio:.1%}) exceeds threshold ({max_unknown_pricing_ratio:.1%})."
        )

    if cost_attribution_failure:
        is_blocked = True
        reasons.append("Blocked: FinOps cost attribution completeness failure detected.")

    # 3. Incident checks
    sev1_sev2 = [
        inc
        for inc in open_incidents
        if inc.get("severity") in (IncidentSeverityEnum.SEV1.value, IncidentSeverityEnum.SEV2.value)
    ]
    if sev1_sev2:
        is_blocked = True
        reasons.append(f"Blocked by {len(sev1_sev2)} active critical incident(s) (SEV1/SEV2).")

    sev3 = [inc for inc in open_incidents if inc.get("severity") == IncidentSeverityEnum.SEV3.value]
    if sev3:
        is_warned = True
        reasons.append(f"Warning: {len(sev3)} open moderate incident(s) (SEV3).")

    # 4. Error budget check
    if error_budget_remaining_pct is not None:
        if error_budget_remaining_pct <= min_budget_remaining_pct:
            is_blocked = True
            reasons.append(
                f"Blocked: Error budget remaining ({error_budget_remaining_pct:.1f}%) is at or below threshold ({min_budget_remaining_pct:.1f}%)."
            )
        elif error_budget_remaining_pct <= (min_budget_remaining_pct * 2.0):
            is_warned = True
            reasons.append(
                f"Warning: Error budget remaining ({error_budget_remaining_pct:.1f}%) is in cautionary range."
            )

    # 5. Recent error rate check
    if recent_error_rate is not None and recent_error_rate > max_error_rate:
        is_blocked = True
        reasons.append(
            f"Blocked: Recent error rate ({recent_error_rate:.3f}) exceeds maximum allowed threshold ({max_error_rate:.3f})."
        )

    if is_blocked:
        return ReleaseGateDecisionEnum.BLOCK, reasons
    if is_warned:
        return ReleaseGateDecisionEnum.WARN, reasons

    reasons.append("All SRE health, incident, and error budget gates passed. Release permitted.")
    return ReleaseGateDecisionEnum.ALLOW, reasons
