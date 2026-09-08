# Production Readiness Evaluation & Scorecard Engine

## 1. Readiness Decision Matrix

The `ProductionReadinessEvaluator` (`backend/app/reliability/readiness.py`) provides an automated, objective gate for production releases.

| Decision | Criteria | Action |
|----------|----------|--------|
| **`READY`** | Composite score $\ge 90.0$, 0 hard blockers, automated tests 100% passing, tenant isolation verified, zero security fail-open vulnerabilities. | Deployment allowed through CI/CD gate. |
| **`READY_WITH_WARNINGS`** | Composite score between $75.0$ and $89.9$, 0 hard blockers, non-critical warnings (e.g., minor latency variance or high queue lag). | Manual SRE sign-off required. |
| **`NOT_READY`** | Composite score $< 75.0$ OR any hard blocker present. | CI/CD gate immediately blocked (`RELEASE_GATE = BLOCK`). |

---

## 2. Hard Blockers

The following violations automatically trigger a `NOT_READY` decision regardless of other scores:
- **Tenant Isolation Breach**: Any query or cache leak across `organization_id` boundaries.
- **Security Fail-Open**: Authorization or rate limiter failure granting unauthorized access on error.
- **Silent Data Corruption**: Uncommitted transactions or inconsistent database states.
- **Automated Test Failures**: Any failure in the core test regression suite.
- **Unbounded Retry Storm**: System failing to employ jittered exponential backoff under dependency failure.

---

## 3. Reliability Scorecard Dimensions

Scorecards are calculated on a deterministic 100-point scale:

$$\text{Composite Score} = 0.15 \times S_{\text{detection}} + 0.25 \times S_{\text{recovery}} + 0.25 \times S_{\text{integrity}} + 0.15 \times S_{\text{degradation}} + 0.10 \times S_{\text{isolation}} + 0.10 \times S_{\text{slo}}$$

- **Detection Score ($S_{\text{detection}}$)**: Evaluates whether faults triggered monitoring within target MTTD.
- **Recovery Score ($S_{\text{recovery}}$)**: Evaluates whether services successfully self-healed within target MTTR.
- **Integrity Score ($S_{\text{integrity}}$)**: 100 if zero corrupt records, 0 if data corruption detected.
- **Degradation Score ($S_{\text{degradation}}$)**: Evaluates graceful fallback (e.g. cached response or polite 503 rather than unhandled 500).
- **Isolation Score ($S_{\text{isolation}}$)**: 100 if strict tenant boundary maintained under load/failure.
- **SLO Score ($S_{\text{slo}}$)**: Based on remaining error budget after scenario execution.

---

## 4. Auditing & Reporting

Every readiness evaluation generates an immutable record in `production_readiness_records` with:
- Evaluation timestamp and actor/service name.
- Factor-by-factor breakdown (Automated Tests, Security, Reliability, Data Integrity, Tenant Isolation).
- Full list of identified warnings and blockers.
- REST endpoint access: `GET /api/v1/reliability/readiness`.
