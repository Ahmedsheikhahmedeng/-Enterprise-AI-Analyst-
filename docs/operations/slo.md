# Service Level Indicators (SLI), Objectives (SLO) & Error Budget Engine

## 1. Mathematical Definitions

### Availability ($A$)
$$A = \frac{\text{successful\_requests}}{\text{total\_requests}}$$
* **Boundary**: $0.0 \le A \le 1.0$
* **Edge Case**: If $\text{total\_requests} = 0$, $A = 1.0$ (no failures observed).

### Error Rate ($E$)
$$E = \frac{\text{failed\_requests}}{\text{total\_requests}}$$
* **Boundary**: $0.0 \le E \le 1.0$
* **Edge Case**: If $\text{total\_requests} = 0$, $E = 0.0$.

### Latency Percentiles
Evaluated using ranked interpolation:
* $P_{50}$: Median latency in milliseconds.
* $P_{95}$: 95th percentile latency.
* $P_{99}$: 99th percentile latency.
* Invariant: $P_{50} \le P_{95} \le P_{99}$.

### Saturation ($S$)
$$S = \frac{\text{used\_capacity}}{\text{total\_capacity}}$$
* **Boundary**: Clamped to $[0.0, 1.0]$.

---

## 2. Error Budget Accounting

For an objective target $T \in [0.0, 1.0]$:
* $\text{budget\_total} = 1.0 - T$
* $\text{budget\_consumed} = \max(0.0, E)$
* $\text{budget\_remaining} = \max(0.0, \text{budget\_total} - \text{budget\_consumed})$
* $\text{budget\_remaining\_percent} = \left( \frac{\text{budget\_remaining}}{\text{budget\_total}} \right) \times 100\%$

### Status Classification
* **BREACHED**: $\text{budget\_remaining} \le 0.0$ or actual value below critical threshold.
* **AT_RISK**: $\text{budget\_remaining\_percent} < 20.0\%$ or actual value below warning threshold.
* **HEALTHY**: Normal operation within approved budget.

---

## 3. Multi-Window Burn Rate Policy

Burn rate quantifies how quickly an error budget is being consumed relative to standard pacing:
$$\text{burn\_rate} = \frac{\text{actual\_error\_rate}}{\text{allowed\_error\_rate}}$$
where $\text{allowed\_error\_rate} = 1.0 - T$.

### Multi-Window Alerting Policy
To prevent false alarms from brief transient spikes, alerts trigger only when both fast and slow windows exceed their thresholds:
* **Critical Burn Alert**:
  $$\text{Fast Burn (e.g. 5m)} \ge 14.4 \times \quad \text{AND} \quad \text{Slow Burn (e.g. 1h)} \ge 3.0 \times$$
  Consumes $2\%$ of error budget in 1 hour.
* **Warning Burn Alert**:
  $$\text{Fast Burn (e.g. 30m)} \ge 7.2 \times \quad \text{AND} \quad \text{Slow Burn (e.g. 6h)} \ge 1.5 \times$$
