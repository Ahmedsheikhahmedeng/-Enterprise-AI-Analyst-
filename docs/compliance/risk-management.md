# Security Findings & Risk Management

> [!NOTE]
> **Explicit Certification Boundary**: This implementation provides technical control readiness and evidence management. It does not constitute SOC 2, ISO 27001, GDPR, HIPAA, or any other formal certification.

---

## 1. Vulnerability Ingestion & Findings

Findings are ingested via the `VulnerabilitySource` parser supporting:
- **Bandit**: Static application security testing (SAST) for Python code.
- **pip-audit**: Dependency vulnerability analysis and CVE matching.
- **Gitleaks**: Secrets detection and token entropy scanning.

Findings are mapped to `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW` severities.

---

## 2. Risk Acceptance Governance

1. **Privileged Approval for CRITICAL Findings**: Risk acceptance for a `CRITICAL` severity finding strictly requires an approved `privileged_approval_id` from the TASK 32 Governance FSM.
2. **Explicit Expiration**: All accepted risks carry an `expires_at` timestamp. Expired acceptances automatically revert to unaccepted states, preventing forgotten security exemptions.
3. **Release Gate Blocking**: Any unaccepted `CRITICAL` finding immediately causes the SRE Release Safety Gate to return `BLOCK`.
