# Release Safety Gates & Automated Pre-Deployment Evaluation

## 1. Overview

The Release Safety Gate (`/api/v1/sre/release-gates/evaluate`) evaluates the live operational state of a target service before new deployments are approved. It bridges production operations with CI/CD delivery pipelines.

---

## 2. Evaluation Criteria

The gate evaluates three live dimensions:

1. **Active Incidents**:
   * Any open **SEV1** or **SEV2** incident immediately causes a **BLOCK**.
   * Any open **SEV3** incident generates a **WARN**.
2. **Error Budget Availability**:
   * If remaining error budget $\le \text{min\_budget\_remaining\_pct}$ (default 10%), returns **BLOCK**.
   * If remaining error budget is between $10\%$ and $20\%$, returns **WARN**.
3. **Recent Error Rate**:
   * If observed error rate over recent window $> \text{max\_error\_rate}$ (default 5%), returns **BLOCK**.

---

## 3. Decision Outcomes

* `ALLOW`: All health criteria and error budget thresholds are satisfied. Release may proceed.
* `WARN`: Cautionary conditions detected (e.g. moderate incident or diminishing error budget). Deployment allowed with explicit acknowledgment.
* `BLOCK`: Deployment is prohibited. The gate provides a deterministic list of reasons explaining the block.

---

## 4. Architectural Boundaries

* The gate does not perform deployments or rollback operations itself.
* It functions as an explainable, auditable SRE policy verification checkpoint for CI/CD and deployment orchestrators.
