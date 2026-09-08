export type OperationalStatus = "HEALTHY" | "DEGRADED" | "CRITICAL" | "UNKNOWN" | "MAINTENANCE";

export type AlertSeverity = "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type AlertStatus = "FIRING" | "ACKNOWLEDGED" | "RESOLVED" | "SUPPRESSED";

export type IncidentSeverity = "SEV1" | "SEV2" | "SEV3" | "SEV4";
export type IncidentStatus = "OPEN" | "ACKNOWLEDGED" | "INVESTIGATING" | "MITIGATED" | "RESOLVED" | "CLOSED";

export type DependencyStatus = "HEALTHY" | "DEGRADED" | "UNHEALTHY" | "UNKNOWN";

export interface PlatformOverview {
  operational_status: OperationalStatus;
  availability_pct: number;
  error_rate_pct: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  latency_p99_ms: number;
  firing_alerts_count: number;
  open_incidents_count: number;
  sev1_incidents_count: number;
  active_maintenance: boolean;
  evaluated_at: string;
}

export interface SREAlert {
  id: string;
  fingerprint: string;
  name: string;
  description?: string;
  service: string;
  severity: AlertSeverity;
  status: AlertStatus;
  source: string;
  metric: string;
  value?: number;
  threshold?: number;
  starts_at: string;
  last_seen_at: string;
  count: number;
  trace_id?: string;
}

export interface IncidentEvent {
  id: string;
  incident_id: string;
  event_type: string;
  actor?: string;
  message: string;
  created_at: string;
}

export interface Incident {
  id: string;
  title: string;
  description?: string;
  service: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  opened_at: string;
  acknowledged_at?: string;
  mitigated_at?: string;
  resolved_at?: string;
  closed_at?: string;
  root_cause?: string;
}

export interface IncidentMetrics {
  total_incidents: number;
  open_incidents: number;
  mtta_seconds?: number;
  mttr_seconds?: number;
  mttr_p95_seconds?: number;
  by_severity: Record<string, number>;
  by_service: Record<string, number>;
}

export interface DependencyItem {
  name: string;
  service: string;
  status: DependencyStatus;
  latency_ms: number;
  error_rate: number;
  message?: string;
}

export interface Runbook {
  id: string;
  name: string;
  description?: string;
  service: string;
  trigger: string;
  symptoms: string[];
  diagnostic_steps: string[];
  safe_actions: string[];
  rollback_notes?: string;
  owner: string;
  version: number;
  is_published: boolean;
}
