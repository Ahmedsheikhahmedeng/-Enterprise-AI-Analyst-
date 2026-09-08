# Privacy Governance & PII Protection

> [!NOTE]
> **Explicit Certification Boundary**: This implementation provides technical control readiness and evidence management. It does not constitute SOC 2, ISO 27001, GDPR, HIPAA, or any other formal certification.

---

## 1. PII Detection Categories

The privacy engine scans input text and dataset contents for 9 core identifier categories:
1. `EMAIL`
2. `PHONE`
3. `IP`
4. `CREDIT_CARD`
5. `NATIONAL_ID` (SSN, National ID)
6. `PASSPORT`
7. `BANK_ACCOUNT` (IBAN)
8. `PERSON_NAME`
9. `ADDRESS`

> [!WARNING]
> **Regex Heuristic Notice**: Regex pattern matching provides deterministic detection for structured identifiers. It cannot guarantee 100% recall for unformatted names or novel address formats.

---

## 2. Privacy Actions

Configured per tenant and data classification tier:
- **`MASK`**: Replaces matches with sanitized tokens (e.g. `[REDACTED_EMAIL]`).
- **`BLOCK`**: Rejects execution and raises `PolicyViolationError`.
- **`ALLOW`**: Permits processing for authorized internal contexts.

All privacy events (`PII_DETECTED`, `PII_MASKED`, `PII_EXPORT_BLOCKED`) are recorded in audit logs with actor, timestamp, and resource reference, with **zero raw sensitive values stored**.
