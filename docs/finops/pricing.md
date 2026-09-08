# Model Pricing Registry & Calculation Determinism

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. Configured Pricing vs. Actual Bills

All pricing stored in the platform registry is categorized as:
```
source = "CONFIGURED_ESTIMATE"
```
Under no circumstances are unverified configured estimates presented as verified provider invoices.

---

## 2. Deterministic Calculation Formula

Cost calculations are computed using exact decimal arithmetic without floating-point rounding errors:

$$\text{Input Cost} = \frac{\text{Input Tokens}}{1{,}000{,}000} \times \text{Input Price}$$

$$\text{Output Cost} = \frac{\text{Output Tokens}}{1{,}000{,}000} \times \text{Output Price}$$

$$\text{Cached Cost} = \frac{\text{Cached Tokens}}{1{,}000{,}000} \times \text{Cached Price}$$

$$\text{Total Cost} = \text{Input Cost} + \text{Output Cost} + \text{Cached Cost}$$

---

## 3. Versioning & Effective Date Windows

Pricing rates are strictly versioned. When provider pricing alters:
1. A new version record is inserted with `effective_from = <date>`.
2. The previous version's `effective_until` is closed.
3. Historical `CostEvent` entries continue pointing to their original `pricing_version`.

---

## 4. Handling Unknown Pricing

If a request runs on a model lacking an active pricing registry entry:
- The request does **NOT** fail.
- The event is recorded with `pricing_version = 0` and `estimated_cost = 0.0`.
- The system flags `needs_pricing_review = true` and generates an audit log.
- Fake or invented token prices are strictly prohibited.
