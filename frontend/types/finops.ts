export type CostOperation =
  | "CHAT"
  | "RAG"
  | "SQL"
  | "EMBEDDING"
  | "RERANK"
  | "AGENT"
  | "EVALUATION"
  | "REPORT"
  | "MEMORY";

export type BudgetScope = "ORGANIZATION" | "USER" | "PROJECT" | "FEATURE" | "AGENT" | "ENVIRONMENT";
export type BudgetPeriod = "DAILY" | "WEEKLY" | "MONTHLY" | "CUSTOM";
export type BudgetState = "SPENDING" | "WARNING" | "CRITICAL" | "EXHAUSTED";

export type QuotaType = "REQUESTS" | "TOKENS" | "COST" | "CONCURRENCY";
export type QuotaEnforcementMode = "ALLOW" | "WARN" | "THROTTLE" | "BLOCK";

export type FinOpsSeverity = "INFO" | "WARNING" | "ERROR" | "CRITICAL";
export type AnomalyType =
  | "SUDDEN_SPIKE"
  | "UNUSUAL_DAILY_COST"
  | "UNUSUAL_TOKEN_VOLUME"
  | "UNUSUAL_COST_PER_REQUEST"
  | "MODEL_COST_SHIFT"
  | "TENANT_USAGE_SPIKE";

export type RecommendationType =
  | "SWITCH_TO_LOWER_COST_MODEL"
  | "REDUCE_CONTEXT"
  | "ENABLE_CACHING"
  | "REDUCE_MAX_OUTPUT"
  | "REVIEW_AGENT_LOOP"
  | "REVIEW_RERANK_TOP_K";

export type ReconciliationStatus = "MATCHED" | "MISSING" | "DUPLICATED" | "MISMATCHED" | "UNKNOWN_PRICING";
export type ReadinessDecision = "READY" | "READY_WITH_WARNINGS" | "NOT_READY";

export interface CostEvent {
  id: string;
  organization_id?: string;
  user_id?: string;
  request_id?: string;
  provider: string;
  model: string;
  operation: CostOperation;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  total_tokens: number;
  estimated_cost: number | string;
  currency: string;
  pricing_version: number;
  timestamp: string;
  is_retry: boolean;
  is_failed: boolean;
  metadata_payload?: Record<string, unknown>;
}

export interface ModelPricing {
  id: string;
  provider: string;
  model: string;
  version: number;
  input_price_per_1m: number | string;
  output_price_per_1m: number | string;
  cached_input_price_per_1m?: number | string | null;
  currency: string;
  effective_from: string;
  effective_until?: string | null;
  source: string;
  is_active: boolean;
}

export interface Budget {
  id: string;
  organization_id: string;
  scope: BudgetScope;
  scope_id?: string | null;
  parent_budget_id?: string | null;
  period: BudgetPeriod;
  limit_amount: number | string;
  currency: string;
  warning_percent: number;
  critical_percent: number;
  enabled: boolean;
  starts_at: string;
  ends_at?: string | null;
  created_by?: string | null;
}

export interface Quota {
  id: string;
  organization_id: string;
  quota_type: QuotaType;
  scope: BudgetScope;
  scope_id?: string | null;
  limit_value: number | string;
  period_seconds: number;
  enforcement_mode: QuotaEnforcementMode;
  enabled: boolean;
}

export interface CostAnomaly {
  id: string;
  organization_id: string;
  anomaly_type: AnomalyType;
  severity: FinOpsSeverity;
  status: "OPEN" | "RESOLVED" | "DISMISSED";
  baseline_amount: number | string;
  actual_amount: number | string;
  deviation_percent: number;
  estimated_impact: number | string;
  description: string;
  affected_entity?: string | null;
  detected_at: string;
  resolved_at?: string | null;
}

export interface CostForecast {
  id: string;
  organization_id: string;
  period: string;
  actual_to_date: number | string;
  forecasted_total: number | string;
  budget_limit: number | string;
  expected_overrun: number | string;
  confidence: number;
  forecast_method: string;
}

export interface OptimizationRecommendation {
  id: string;
  organization_id: string;
  recommendation_type: RecommendationType;
  status: "OPEN" | "APPLIED" | "DISMISSED";
  title: string;
  description: string;
  current_cost: number | string;
  expected_saving: number | string;
  quality_impact: string;
  latency_impact: string;
  confidence: number;
  evidence: Record<string, unknown>;
}

export interface CostReconciliation {
  id: string;
  organization_id?: string | null;
  status: ReconciliationStatus;
  period_start: string;
  period_end: string;
  matched_count: number;
  missing_count: number;
  duplicated_count: number;
  mismatched_count: number;
  unknown_pricing_count: number;
  discrepancy_amount: number | string;
  details: Record<string, unknown>;
}

export interface FinOpsOverview {
  current_spend: number | string;
  forecasted_spend: number | string;
  budget_total: number | string;
  remaining_budget: number | string;
  utilization_percent: number;
  top_model: string;
  top_provider: string;
  top_feature: string;
  open_anomalies_count: number;
  potential_savings: number | string;
  attribution_completeness_percent: number;
  readiness_status: ReadinessDecision;
  disclaimer: string;
}
