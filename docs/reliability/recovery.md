# Automated Recovery & Timeline Telemetry

## 1. Lifecycle Timeline Engine

During a chaos experiment or real operational incident, the platform records precise timestamps to calculate mean-time metrics:

```
T0: Fault Injected (injected_at)
 │
 ├──▶ T1: First Healthcheck / Monitor Failure (detected_at)
 │        └── MTTD = T1 - T0
 │
 ├──▶ T2: SRE Alert Fired or Incident Opened (acknowledged_at)
 │        └── MTTA = T2 - T1
 │
 ├──▶ T3: Fault Injector Teardown / Subsystem Reconnection (fault_recovered_at)
 │
 └──▶ T4: Invariant Verification Passes / Health Restored (fully_recovered_at)
          └── MTTR = T4 - T3
          └── Total Time to Recovery = T4 - T0
```

### Mathematical Definitions
- **MTTD (Mean Time to Detect)**:
  $$\text{MTTD} = \Delta(T_{\text{detected}} - T_{\text{injected}})$$
  *Target*: $< 5.0\text{s}$ for core dependencies; $< 15.0\text{s}$ for third-party APIs.
- **MTTA (Mean Time to Acknowledge)**:
  $$\text{MTTA} = \Delta(T_{\text{alert\_fired}} - T_{\text{detected}})$$
  *Target*: $< 2.0\text{s}$ for automated SRE alert generation and deduplication.
- **MTTR (Mean Time to Recover)**:
  $$\text{MTTR} = \Delta(T_{\text{healthy}} - T_{\text{restoration\_started}})$$
  *Target*: $< 30.0\text{s}$ for in-process retries; $< 120.0\text{s}$ for external reconnections.
- **Time to Recovery (TTR)**:
  $$\text{TTR} = \Delta(T_{\text{healthy}} - T_{\text{injected}})$$

---

## 2. Recovery Telemetry Engine Implementation

The `RecoveryTimeline` class in `backend/app/reliability/recovery.py` aggregates timeline points and verifies that targets are met:

```python
timeline = RecoveryTimeline(
    injected_at=start_time,
    detected_at=first_alert_time,
    acknowledged_at=incident_time,
    recovered_at=end_time,
)

mttd = timeline.calculate_mttd()
mtta = timeline.calculate_mtta()
mttr = timeline.calculate_mttr()
ttr = timeline.calculate_total_time_to_recovery()
```

---

## 3. SRE Platform Integration (TASK 37 Synergy)

Every chaos scenario automatically ties into the SRE subsystems built in TASK 37:
1. **SLO Impact Calculation**:
   Calculates the percentage of degradation against target SLOs (e.g., API Availability 99.9%, Latency p95 < 500ms).
2. **Error Budget Burn**:
   Translates outage seconds into consumed error budget percentage.
3. **Alert Deduplication & Incident Creation**:
   Spikes generate deduplicated alerts under the appropriate service fingerprint (`api_gateway`, `database`, `workers`, `llm_gateway`).
4. **Release Safety Gate**:
   Evaluates whether the system meets the deployment release criteria (`ALLOW`, `WARN`, or `BLOCK`).
