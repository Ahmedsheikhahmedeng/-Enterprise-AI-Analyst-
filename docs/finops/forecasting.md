# Spend Trajectory Forecasting & Burn Rate

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. Linear Velocity Projections

Spend forecasting uses deterministic linear extrapolation across active billing cycles:

$$\text{Daily Velocity} = \frac{\text{Actual To Date}}{\text{Elapsed Days}}$$

$$\text{Forecasted Period End} = \text{Actual To Date} + (\text{Daily Velocity} \times \text{Remaining Days})$$

$$\text{Expected Overrun} = \max(0, \text{Forecasted Period End} - \text{Budget Limit})$$

---

## 2. Confidence Calibration

Confidence scores scale smoothly between $0.50$ (at period start) and $0.95$ (as elapsed days approach period completion):

$$\text{Confidence} = 0.50 + \left(0.45 \times \frac{\text{Elapsed Days}}{\text{Total Days}}\right)$$
