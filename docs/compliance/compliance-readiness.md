# Compliance Readiness & Continuous Assessment

> [!NOTE]
> **Explicit Certification Boundary**: This implementation provides technical control readiness and evidence management. It does not constitute SOC 2, ISO 27001, GDPR, HIPAA, or any other formal certification.

---

## 1. Compliance Score Formulation

The compliance score is deterministically computed from weighted control assessments:
$$\text{Score} = \frac{\sum_{c \in C} w_c \cdot s_c}{\sum_{c \in C} w_c}$$
Where weights are configured as:
- `CRITICAL`: 5.0
- `HIGH`: 3.0
- `MEDIUM`: 2.0
- `LOW`: 1.0

---

## 2. Readiness Decisions & Hard Blockers

1. **`READY`**: All mandatory controls pass, no open critical findings, audit integrity is valid, and score $\ge 90\%$.
2. **`READY_WITH_WARNINGS`**: Score $\ge 70\%$ and no hard blockers, but non-critical controls warn (e.g. stale evidence).
3. **`NOT_READY`**: Immediate blocker present:
   - Any open, unaccepted `CRITICAL` finding.
   - Any failed mandatory control (e.g. `SEC-TENANT-001`, `SEC-TENANT-002`).
   - Audit hash chain mismatch or integrity failure.
   - Tenant isolation verification failure.
