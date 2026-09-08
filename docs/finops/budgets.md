# Hierarchical Budgets & Preflight Enforcement

> **Explicit Billing Boundary Disclaimer**  
> *This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.*

---

## 1. Budget Hierarchy & Scopes

Budgets can be created at multiple structural scopes:
```
Organization
  └── Project
        └── Agent
              └── User
```
Supported scopes: `ORGANIZATION`, `USER`, `PROJECT`, `FEATURE`, `AGENT`, `ENVIRONMENT`.

---

## 2. Budget State Lifecycle

Utilization is computed as:
$$\text{Utilization} = \frac{\text{Current Spent}}{\text{Limit Amount}} \times 100\%$$

| State | Condition | Platform Behavior |
| :--- | :--- | :--- |
| `SPENDING` | $< \text{warning\_percent}$ (e.g. $< 80\%$) | Unrestricted normal operations |
| `WARNING` | $\ge \text{warning\_percent}$ (e.g. $\ge 80\%$) | Warning logged, notifications issued |
| `CRITICAL` | $\ge \text{critical\_percent}$ (e.g. $\ge 95\%$) | High-priority FinOps alert emitted |
| `EXHAUSTED` | $\ge 100\%$ | Block downstream invocations or trigger approval |

---

## 3. Preflight Cost Estimation

Before executing high-cost AI operations (e.g. multi-step agent plans, large document indexing, batch benchmark evaluations):
1. An initial estimate of `estimated_cost` is calculated.
2. The `BudgetEngine.preflight_check` verifies that `current_spent + estimated_cost <= limit`.
3. If breached, the operation is prevented from starting (`BLOCK` or `APPROVAL`).
