# Immutable Usage Ledger & Cost Attribution

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. The Immutable Ledger (`CostEvent`)

Historical usage accounting is **strictly append-only**. Destructive updates or row deletions of past usage are mathematically and architecturally prohibited.

Each `CostEvent` record stores:
- `organization_id`: Tenant attribution (mandatory for tenant-owned workloads).
- `user_id`: Optional actor reference.
- `request_id`, `trace_id`: Cross-layer correlation handles.
- `agent_session_id`, `job_id`: Execution context tags.
- `provider`, `model`, `operation`: Categorization tags (`CHAT`, `RAG`, `SQL`, `EMBEDDING`, `RERANK`, `AGENT`, `EVALUATION`).
- `input_tokens`, `output_tokens`, `cached_tokens`, `total_tokens`.
- `estimated_cost`: High-precision deterministic calculation (`NUMERIC(14, 8)`).
- `pricing_version`: The integer version identifier of model pricing applied.
- `is_retry`, `is_failed`: Telemetry flags used to compute wasted financial cost.

---

## 2. Compensating Adjustments (`CostCorrection`)

When an invoice reconciliation discrepancy or downstream correction is required:
- The historical `CostEvent` remains completely untouched.
- An append-only `CostCorrection` is inserted containing:
  - `original_event_id`: Reference to the event being rectified.
  - `adjustment_cost`: Positive or negative monetary adjustment amount.
  - `reason`: Justification text for audit tracking.
  - `actor`: Identity of the administrator or automated reconciler.
  - `corrected_at`: Audit timestamp.

---

## 3. Privacy & Data Minimization Invariants

The usage ledger strictly adheres to enterprise privacy and security governance (TASK 39):
- **NO RAW PROMPTS**: Storing raw input text in FinOps tables is forbidden.
- **NO COMPLETIONS**: Storing generated model outputs in FinOps tables is forbidden.
- **NO CREDENTIALS / API KEYS**: Authentication tokens and secrets are scrubbed before metadata persistence.
