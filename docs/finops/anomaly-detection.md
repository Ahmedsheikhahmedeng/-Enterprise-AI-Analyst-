# Deterministic Cost & Token Anomaly Detection

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. Methodology

Cost and token surges are discovered using testable, deterministic statistical techniques (moving average baselines and percentage deviations) rather than opaque black-box heuristics.

---

## 2. Detection Criteria

- **Sudden Cost Spike**: Triggered when the current period or hourly spend exceeds the historical rolling baseline by $\ge 100\%$ (2x).
- **Token Volume Surge**: Triggered when prompt or completion token volume exceeds the moving average by $\ge 150\%$.
- **Severity Mapping**:
  - $\text{Deviation} \ge 300\%$: `CRITICAL`
  - $\text{Deviation} \ge 150\%$: `ERROR`
  - $\text{Deviation} \ge 100\%$: `WARNING`

---

## 3. SRE & Incident Correlation

Severe anomalies (`CRITICAL`) integrate directly into the Site Reliability Engineering layer (TASK 37) to generate operational incidents without duplicating alerting infrastructures.
