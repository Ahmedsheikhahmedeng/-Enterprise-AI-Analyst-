# Enterprise Observability Operations & SRE Architecture

## Overview
This document outlines the Enterprise Site Reliability Engineering (SRE) architecture, principles, mathematical formulas, and operational models deployed across the platform.

## Architectural Layers
```text
Clients & Next.js Operations UI (/operations)
                 ↓
      FastAPI SRE REST API (/api/v1/sre)
                 ↓
          SRE Service Layer
                 ↓
  ┌──────────────┼──────────────┬──────────────┐
SLI/SLO     Error Budget    Alert Ingest    Incidents
Engine       & Burn Rate    & Dedup FSM     & Timeline
  └──────────────┼──────────────┴──────────────┘
                 ↓
        SRERepository (PostgreSQL)
                 ↓
  Underlying Infrastructure & Telemetry (TASK 21 & TASK 36)
```

## Implemented Capabilities
- **Deterministic SLI Metric Evaluation**: Availability ($A$), Error Rate ($E$), Latency Percentiles ($P_{50}, P_{95}, P_{99}$), Saturation ($S$), Queue Health, Worker Fleet Health, Stream Reliability.
- **Error Budget Accounting**: Total budget, consumed budget, remaining budget, remaining percentage clamped strictly to $[0.0, 100.0]\%$.
- **Dual-Window Burn Rate Engine**: Fast burn & slow burn pairs preventing false positive alerts.
- **Alert Deduplication & Fingerprinting**: Stable SHA-256 fingerprinting based on service, metric, rule name, and severity (no timestamps).
- **Incident Lifecycle FSM**: Finite State Machine enforcing legal status transitions (`OPEN -> ACKNOWLEDGED -> INVESTIGATING -> MITIGATED -> RESOLVED -> CLOSED`) with immutable timeline tracking.
- **Runbook Safety Policy**: Automated scanning to prohibit destructive commands (`rm -rf`, `DROP TABLE`, `kill -9`).
- **Release Safety Gate**: Automated pre-deployment evaluation returning `ALLOW`, `WARN`, or `BLOCK` based on open critical incidents and error budget availability.

## What is Implemented vs. Abstractions
| Component | Status | Description |
| :--- | :--- | :--- |
| SLI / SLO Engine | **Implemented** | Deterministic calculations over actual sliding windows |
| Error Budget Engine | **Implemented** | Mathematical accounting with boundary guarantees |
| Alert Fingerprint & Dedup | **Implemented** | SHA-256 fingerprinting with counter increment in PostgreSQL |
| Maintenance Window Suppression | **Implemented** | Suppresses alerts during maintenance; critical security alerts exempted |
| Incident FSM & Timeline | **Implemented** | Enforced transition rules with immutable `IncidentEvent` ledger |
| MTTA & MTTR Analytics | **Implemented** | Average, median, and P95 calculated from timestamps |
| Release Safety Gates | **Implemented** | Pre-deployment evaluator returning ALLOW/WARN/BLOCK |
| In-App Alert Notifications | **Implemented** | `InAppNotificationProvider` records in-app notifications |
| PagerDuty / Opsgenie / Slack | **Abstraction Only** | Abstract `NotificationProvider` interface; no external dependencies |
| Automated Destructive Remediation | **Forbidden** | Not implemented; runbooks are read-only / diagnostic by design |
