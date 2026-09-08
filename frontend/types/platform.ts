/**
 * Canonical Platform & Frontend Types — TASK 35
 * Strict contract parity with TASK 34 Backend APIs.
 */

export interface PaginationMeta {
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
}

export interface PaginatedData<T> {
  items: T[];
  pagination: PaginationMeta;
}

export interface ErrorDetail {
  loc?: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiError {
  code: string;
  message: string;
  details: ErrorDetail[];
  retryable: boolean;
  request_id?: string | null;
}

export interface ResponseMeta {
  request_id?: string | null;
  timestamp: string;
  duration_ms?: number | null;
}

export interface ApiResponse<T = unknown> {
  data: T | null;
  error: ApiError | null;
  meta: ResponseMeta;
  pagination?: PaginationMeta | null;
}

// Orchestration Enums
export type OrchestrationMode = "AUTO" | "RAG" | "SQL" | "HYBRID" | "GRAPH";
export type ResponseStyle = "CONCISE" | "STANDARD" | "DETAILED" | "EXECUTIVE";
export type ExecutionStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED" | "APPROVAL_REQUIRED";
export type EvidenceSourceType = "VECTOR_CHUNK" | "SQL_RECORD" | "GRAPH_EDGE" | "SEMANTIC_METRIC" | "EXTERNAL_DOC";

// Ask Request & Response
export interface AskRequest {
  question: string;
  mode?: OrchestrationMode;
  response_style?: ResponseStyle;
  stream?: boolean;
  conversation_id?: string | null;
  parameters?: Record<string, unknown>;
}

export interface Citation {
  citation_id: string; // e.g. "[S1]"
  source_type: EvidenceSourceType;
  title: string;
  source_uri?: string | null;
  snippet: string;
  trust_level?: string;
  confidence?: number;
}

export interface EvidenceItem {
  id: string;
  source_type: EvidenceSourceType;
  title: string;
  snippet: string;
  source_uri?: string | null;
  score?: number;
  trust_level?: string;
  metadata?: Record<string, unknown>;
}

export interface EvidenceResponse {
  execution_id: string;
  items: EvidenceItem[];
  total_items: number;
}

export interface AskResponsePayload {
  execution_id: string;
  conversation_id?: string | null;
  status: ExecutionStatus;
  question: string;
  mode: OrchestrationMode;
  answer: string | null;
  evidence: EvidenceItem[];
  citations: Citation[];
  confidence_score?: number | null;
  stage_progress: Record<string, unknown>;
  stream_url?: string | null;
  is_partial: boolean;
  has_conflicts: boolean;
  approval_id?: string | null;
  clarification_needed: boolean;
  suggested_options?: string[] | null;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

// Streaming SSE Types
export type SSEEventType =
  | "execution_started"
  | "query_analyzed"
  | "routing_selected"
  | "semantic_resolved"
  | "graph_expanded"
  | "retrieval_started"
  | "retrieval_completed"
  | "plan_generated"
  | "step_started"
  | "step_completed"
  | "evidence_collected"
  | "verification_started"
  | "verification_completed"
  | "response_chunk"
  | "response_completed"
  | "execution_failed"
  | "approval_required"
  | "execution_cancelled"
  | "execution_stage"
  | "execution_progress";

export interface StreamEvent {
  event: SSEEventType | string;
  execution_id: string;
  timestamp: string;
  sequence: number;
  data: Record<string, unknown>;
}

// Execution Summary & Detail
export interface ExecutionSummary {
  execution_id: string;
  conversation_id?: string | null;
  question: string;
  status: ExecutionStatus;
  mode: OrchestrationMode;
  duration_ms?: number | null;
  created_at: string;
  completed_at?: string | null;
}

export interface ExecutionDetail extends ExecutionSummary {
  answer?: string | null;
  confidence_score?: number | null;
  is_partial: boolean;
  has_conflicts: boolean;
  evidence: EvidenceItem[];
  citations: Citation[];
  error_message?: string | null;
  provenance?: {
    system_version?: string;
    model_version?: string;
    prompt_hash?: string;
    schema_version?: string;
    duration_ms?: number;
  };
}

// Governance & Approvals
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED";

export interface ApprovalItem {
  id: string;
  execution_id?: string;
  resource_id?: string;
  action_type: string;
  risk_level: RiskLevel;
  status: ApprovalStatus;
  reason?: string;
  requested_by?: string;
  created_at: string;
  expires_at?: string | null;
}

// Datasets
export interface DatasetItem {
  id: string;
  name: string;
  source_type: string;
  status: string;
  row_count?: number;
  column_count?: number;
  quality_score?: number;
  null_ratio?: number;
  duplicate_ratio?: number;
  invalid_ratio?: number;
  updated_at: string;
}

// Semantic Catalog
export interface SemanticTerm {
  id: string;
  name: string;
  definition: string;
  status: "DRAFT" | "REVIEW" | "APPROVED" | "PUBLISHED" | "ARCHIVED";
  category?: string;
  created_at: string;
}

export interface SemanticMetric {
  id: string;
  name: string;
  formula?: string;
  status: "DRAFT" | "REVIEW" | "APPROVED" | "PUBLISHED" | "ARCHIVED";
  unit?: string;
  created_at: string;
}

// Continuous Evaluation
export interface EvaluationScorecard {
  suite_id: string;
  name: string;
  overall_quality: number;
  grounding_score: number;
  citation_precision: number;
  retrieval_ndcg: number;
  sql_accuracy: number;
  decision: "PASS" | "WARN" | "FAIL" | "BLOCK_RELEASE";
  delta_from_baseline?: number;
  timestamp: string;
}

// User & Auth Session
export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  organization_id: string;
  organization_name?: string;
  available_organizations?: { id: string; name: string }[];
  permissions: string[];
}
