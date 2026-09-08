# FinOps Readiness & Release Safety Gates

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. Readiness States

The `FinOpsReadinessEvaluator` outputs one of three operational states:
- **`READY`**: All pricing coverage, attribution completeness, and reconciliation criteria pass without blockers.
- **`READY_WITH_WARNINGS`**: Minor non-critical warnings (e.g. minor attribution gap $< 5\%$ or exhausted non-blocking budget).
- **`NOT_READY`**: One or more hard financial blockers are detected.

---

## 2. Hard Release Blockers

The presence of any of the following triggers an immediate `NOT_READY` state and blocks deployment gates:
1. **Tenant Cost Leakage**: Cross-tenant data attribution failures.
2. **Negative Cost / Token Values**: Mathematical or data corruption in the ledger.
3. **Budget Bypass**: Downstream model calls executed without active budget evaluation.
4. **Active Critical Cost Anomalies**: Unresolved $> 300\%$ spend spikes.
5. **Insufficient Model Pricing Coverage**: Active models missing pricing rates ($< 50\%$).
