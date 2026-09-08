# Cost Reconciliation & Audit Integrity

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. Audit Reconciliation Purpose

The `ReconciliationEngine` automatically reconciles LLM Gateway transaction logs (`LLMRequest`) against the immutable FinOps ledger (`CostEvent`) to detect:
- **`missing_count`**: Requests executed on the gateway that were omitted from the financial ledger.
- **`duplicated_count`**: Redundant double-attribution records.
- **`mismatched_count`**: Discrepancies between gateway reported token counts and ledger recorded values.
- **`unknown_pricing_count`**: Operations missing versioned pricing.

---

## 2. Cryptographic Checksum Integrity

Reconciliation summaries calculate SHA-256 hashes of matched telemetry records to guarantee that historical cost reports cannot be tampered with after generation.
