export type ScenarioCategory =
  | "DEPENDENCY"
  | "NETWORK"
  | "DATABASE"
  | "QUEUE"
  | "WORKER"
  | "LLM"
  | "STREAMING"
  | "RESOURCE"
  | "RECOVERY"
  | "SECURITY";

export type FaultType =
  | "POSTGRES_UNAVAILABLE"
  | "POSTGRES_LATENCY"
  | "REDIS_UNAVAILABLE"
  | "REDIS_LATENCY"
  | "QDRANT_UNAVAILABLE"
  | "QDRANT_LATENCY"
  | "LLM_TIMEOUT"
  | "LLM_5XX"
  | "LLM_429"
  | "LLM_MALFORMED"
  | "LLM_FAILOVER"
  | "WORKER_CRASH"
  | "QUEUE_BACKLOG"
  | "DLQ_TRANSITION"
  | "SSE_DISCONNECT"
  | "SSE_LATENCY"
  | "API_LATENCY"
  | "API_ERROR_SPIKE";

export type ReliabilityRunStatus =
  | "PENDING"
  | "RUNNING"
  | "PASSED"
  | "FAILED"
  | "ABORTED"
  | "SKIPPED";

export type ReadinessDecision =
  | "READY"
  | "READY_WITH_WARNINGS"
  | "NOT_READY";

export interface ReliabilityScenario {
  id: string;
  name: string;
  description: string;
  category: ScenarioCategory;
  severity: string;
  enabled: boolean;
  timeout_seconds: number;
  max_duration_seconds: number;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ReliabilityAssertion {
  id: string;
  run_id: string;
  assertion_type: string;
  status: "PASSED" | "FAILED" | "WARNING";
  description: string;
  evidence: Record<string, unknown>;
  created_at: string;
}

export interface ReliabilityFault {
  id: string;
  run_id: string;
  fault_type: FaultType;
  lifecycle: string;
  injected_at: string;
  recovered_at: string | null;
  parameters: Record<string, unknown>;
  details: Record<string, unknown>;
  created_at: string;
}

export interface ReliabilityRun {
  id: string;
  scenario_id: string;
  environment: string;
  status: ReliabilityRunStatus;
  fault_type: FaultType;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  mttd_seconds: number | null;
  mtta_seconds: number | null;
  mttr_seconds: number | null;
  time_to_recovery_seconds: number | null;
  slo_impact_pct: number;
  error_budget_consumed_pct: number;
  alerts_created_count: number;
  incidents_created_count: number;
  release_gate_verdict: string | null;
  failure_classification: string | null;
  correlation_id: string | null;
  summary: string | null;
  created_at: string;
  faults?: ReliabilityFault[];
  assertions?: ReliabilityAssertion[];
}

export interface ReliabilityScorecard {
  id: string;
  period_start: string;
  period_end: string;
  detection_score: number;
  recovery_score: number;
  integrity_score: number;
  degradation_score: number;
  isolation_score: number;
  slo_score: number;
  composite_score: number;
  total_scenarios_run: number;
  passed_count: number;
  failed_count: number;
  metrics_payload: Record<string, unknown>;
  created_at: string;
}

export interface ProductionReadiness {
  id: string;
  decision: ReadinessDecision;
  evaluator: string;
  composite_score: number;
  evaluation_factors: Record<string, unknown>;
  blockers: string[];
  warnings: string[];
  created_at: string;
}
