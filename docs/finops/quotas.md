# Multi-Dimensional Rate Quotas & Enforcement

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. Quota Dimensions

The FinOps layer enforces consumption limits across four orthogonal dimensions:
- **`REQUESTS`**: Cap on API or gateway invocations over a rolling window (e.g. 500 requests / hour).
- **`TOKENS`**: Cap on total processed token volume (e.g. 10,000,000 tokens / day).
- **`COST`**: Monetary spending ceiling within a given cycle (e.g. $50.00 / week).
- **`CONCURRENCY`**: Maximum parallel asynchronous executions per tenant.

---

## 2. Enforcement Modes

When an incoming operation causes total consumption to exceed quota limits, the system applies the configured enforcement mode:
- **`ALLOW`**: Telemetry recorded; operation proceeds uninterrupted.
- **`WARN`**: Alert emitted to SRE/FinOps; operation proceeds.
- **`THROTTLE`**: Invocations delayed or queued to smooth peak spikes.
- **`BLOCK`**: Operation immediately halted with a 429 / `QuotaExceededError`.
