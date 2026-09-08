# Data Classification & Handling Guardrails

> [!NOTE]
> **Explicit Certification Boundary**: This implementation provides technical control readiness and evidence management. It does not constitute SOC 2, ISO 27001, GDPR, HIPAA, or any other formal certification.

---

## 1. Classification Tiers

Platform datasets, documents, tables, and connectors are classified into five deterministic sensitivity tiers:

1. **`PUBLIC`**: Freely shareable marketing materials, product documentation, and public datasets.
2. **`INTERNAL`**: Standard platform operations, operational logs, and non-sensitive analytical workloads.
3. **`CONFIDENTIAL`**: Proprietary financial records, sensitive metrics, and enterprise customer information.
4. **`RESTRICTED`**: Authentication secrets, encryption keys, PII identifiers, and privileged assets.
5. **`SENSITIVE`**: Protected health data, full payment cards, and government identification numbers.

---

## 2. Guardrail Enforcement Matrix

| Classification Tier | Allowed LLM Providers | External Processing Allowed | Export Governance | Agent Tool Access |
| :--- | :--- | :--- | :--- | :--- |
| **`PUBLIC`** | All active providers | Allowed | Allowed | Unrestricted |
| **`INTERNAL`** | Approved enterprise providers | Allowed | Organization-scoped | Standard tools |
| **`CONFIDENTIAL`** | Pre-approved zero-retention providers | Policy-checked | Governance approval required | Whitelisted tools only |
| **`RESTRICTED`** | Local / on-premise model only | **Blocked** | **Blocked** | Isolated runtime only |
| **`SENSITIVE`** | Redaction mandatory before routing | **Blocked** | **Blocked** | Prohibited |
