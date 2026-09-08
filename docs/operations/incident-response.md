# Incident Response & Lifecycle Management

## 1. Incident Severity Classification

| Severity | Definition | Target MTTA | Target MTTR |
| :--- | :--- | :--- | :--- |
| **SEV1** | Critical platform outage or widespread unavailability of core service | < 5 min | < 1 hour |
| **SEV2** | Major degradation of primary user-facing analysis or retrieval workflows | < 15 min | < 4 hours |
| **SEV3** | Limited degradation or intermittent background task failures | < 1 hour | < 24 hours |
| **SEV4** | Minor operational flaw, cosmetic issue, or non-impacting anomaly | Next business day | Scheduled sprint |

---

## 2. Finite State Machine (FSM)

The incident lifecycle follows strict forward-progress transitions:

```text
    ┌───────────────┐
    │     OPEN      │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ ACKNOWLEDGED  │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ INVESTIGATING │ ◄──┐
    └───────┬───────┘    │ (Mitigation failed)
            │            │
            ▼            │
    ┌───────────────┐    │
    │   MITIGATED   ├────┘
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │   RESOLVED    │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │    CLOSED     │ (Terminal)
    └───────────────┘
```

### Transition Invariants
* Backward transitions from `RESOLVED` to `OPEN` or `INVESTIGATING` are forbidden.
* The `CLOSED` state is terminal: once closed, an incident cannot transition to any other status.
* All state transitions append an immutable `IncidentEvent` recording the actor, timestamp, and message.

---

## 3. MTTA and MTTR Metrics

* **MTTA (Mean Time To Acknowledge)**:
  $$\text{MTTA} = \text{acknowledged\_at} - \text{opened\_at}$$
* **MTTR (Mean Time To Resolve)**:
  $$\text{MTTR} = \text{resolved\_at} - \text{opened\_at}$$
* Aggregated metrics compute average, median, and 95th percentile ($P_{95}$) across resolved incidents.
