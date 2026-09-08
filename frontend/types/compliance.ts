export type ControlStatus = "PASS" | "WARN" | "FAIL" | "NOT_ASSESSED";
export type ControlSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type FindingSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type FindingStatus = "OPEN" | "ACKNOWLEDGED" | "MITIGATING" | "RESOLVED" | "ACCEPTED_RISK";
export type ReadinessDecision = "READY" | "READY_WITH_WARNINGS" | "NOT_READY";

export interface PillarPosture {
  pillar: string;
  status: ControlStatus;
  controls_total: number;
  controls_passed: number;
  details: Record<string, unknown>;
}

export interface SecurityPosture {
  overall_score: number;
  assessed_at: string;
  pillars: Record<string, PillarPosture>;
}

export interface ComplianceReadiness {
  decision: ReadinessDecision;
  score: number;
  passed_controls: number;
  warning_controls: number;
  failed_controls: number;
  blockers: string[];
  warnings: string[];
  evaluated_at: string;
}

export interface ComplianceOverview {
  posture: SecurityPosture;
  readiness: ComplianceReadiness;
  open_critical_findings: number;
  total_findings: number;
  active_legal_holds: number;
  pending_privacy_requests: number;
  active_access_reviews: number;
  audit_integrity_status: "VALID" | "INVALID" | "INCOMPLETE";
  disclaimer: string;
}

export interface LatestAssessment {
  status: ControlStatus;
  score: number;
  assessed_at: string;
  reason: string;
}

export interface ComplianceControl {
  id: string;
  framework: string;
  control_code: string;
  name: string;
  description: string;
  category: string;
  severity: ControlSeverity;
  automated: boolean;
  enabled: boolean;
  version: number;
  latest_assessment?: LatestAssessment;
}

export interface ComplianceEvidence {
  id: string;
  control_id: string;
  organization_id?: string;
  evidence_type: string;
  source: string;
  reference: string;
  hash: string;
  version: number;
  captured_at: string;
  expires_at?: string;
  metadata_payload: Record<string, unknown>;
  actor?: string;
}

export interface RiskAcceptance {
  id: string;
  finding_id: string;
  reason: string;
  accepted_by: string;
  expires_at: string;
  active: boolean;
  privileged_approval_id?: string;
  created_at: string;
}

export interface SecurityFinding {
  id: string;
  control_id?: string;
  severity: FindingSeverity;
  status: FindingStatus;
  title: string;
  description: string;
  source: string;
  owner?: string;
  first_detected_at: string;
  last_detected_at: string;
  resolved_at?: string;
  risk_acceptances?: RiskAcceptance[];
}

export interface DataClassificationRecord {
  id: string;
  resource_type: string;
  resource_id: string;
  classification: "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED" | "SENSITIVE";
  pii_types_detected: string[];
  classified_by: string;
  notes?: string;
  updated_at: string;
}

export interface AccessReviewItem {
  id: string;
  user_id: string;
  email: string;
  role_name: string;
  permissions: string[];
  last_activity_at?: string;
  review_status: "PENDING" | "CONFIRMED" | "REVOKE_RECOMMENDED" | "REVOKED" | "EXPIRED";
  flagged_inactive: boolean;
}

export interface AccessReview {
  id: string;
  title: string;
  initiated_by: string;
  status: "IN_PROGRESS" | "COMPLETED" | "ARCHIVED";
  total_items: number;
  pending_items: number;
  created_at: string;
  completed_at?: string;
  items?: AccessReviewItem[];
}

export interface LegalHold {
  id: string;
  name: string;
  reason: string;
  created_by: string;
  active: boolean;
  starts_at: string;
  ends_at?: string;
  resources: string[];
}

export interface PrivacyRequest {
  id: string;
  user_id: string;
  request_type: string;
  requested_by: string;
  status: "REQUESTED" | "REVIEW_REQUIRED" | "APPROVED" | "EXECUTED" | "REJECTED";
  resources: string[];
  notes?: string;
  created_at: string;
}
