/**
 * Production Typed API Client — TASK 35
 * Encapsulates all backend interactions with CSRF, request correlation,
 * and canonical ApiResponse[T] envelope handling.
 */

import {
  ApiResponse,
  ApiError,
  AskRequest,
  AskResponsePayload,
  EvidenceResponse,
  ExecutionSummary,
  ExecutionDetail,
  PaginatedData,
  ApprovalItem,
  DatasetItem,
  SemanticTerm,
  SemanticMetric,
  EvaluationScorecard,
  StreamEvent,
  User,
} from "@/types/platform";

export class PlatformApiError extends Error {
  code: string;
  details: unknown[];
  retryable: boolean;
  requestId?: string | null;

  constructor(error: ApiError) {
    super(error.message);
    this.name = "PlatformApiError";
    this.code = error.code;
    this.details = error.details || [];
    this.retryable = error.retryable ?? false;
    this.requestId = error.request_id;
  }
}

function getCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

function generateRequestId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${API_BASE_URL}${endpoint}`;
  const requestId = generateRequestId();
  const csrfToken = getCsrfToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Request-ID": requestId,
    ...(options.headers as Record<string, string>),
  };

  if (csrfToken && ["POST", "PUT", "PATCH", "DELETE"].includes(options.method?.toUpperCase() || "")) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: "include", // send HttpOnly cookies
  });

  let payload: ApiResponse<T>;
  try {
    payload = await response.json();
  } catch {
    throw new PlatformApiError({
      code: "INVALID_SERVER_RESPONSE",
      message: `Failed to parse response (status ${response.status})`,
      details: [],
      retryable: response.status >= 500,
      request_id: requestId,
    });
  }

  if (!response.ok || payload.error) {
    const err = payload.error || {
      code: `HTTP_${response.status}`,
      message: response.statusText || "Request failed",
      details: [],
      retryable: response.status >= 500,
      request_id: requestId,
    };
    throw new PlatformApiError(err);
  }

  return payload;
}

export const apiClient = {
  // Ask & Real-time Execution
  ask: {
    submit: (body: AskRequest) =>
      request<AskResponsePayload>("/ask", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    get: (executionId: string) =>
      request<AskResponsePayload>(`/ask/${executionId}`),
    cancel: (executionId: string, reason = "User requested cancellation") =>
      request<{ status: string; cancelled_at: string }>(`/ask/${executionId}/cancel`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),
    getEvidence: (executionId: string) =>
      request<EvidenceResponse>(`/ask/${executionId}/evidence`),
    getReplayEvents: (executionId: string, afterSequence = 0) =>
      request<StreamEvent[]>(`/ask/${executionId}/events?after_sequence=${afterSequence}`),
  },

  // Executions History
  executions: {
    list: (params: { page?: number; pageSize?: number; status?: string; mode?: string } = {}) => {
      const qs = new URLSearchParams();
      if (params.page) qs.set("page", params.page.toString());
      if (params.pageSize) qs.set("page_size", params.pageSize.toString());
      if (params.status) qs.set("status", params.status);
      if (params.mode) qs.set("mode", params.mode);
      return request<PaginatedData<ExecutionSummary>>(`/executions?${qs.toString()}`);
    },
    get: (id: string) => request<ExecutionDetail>(`/executions/${id}`),
  },

  // Approvals & Governance
  approvals: {
    listPending: () => request<ApprovalItem[]>("/approvals/pending"),
    resolve: (approvalId: string, decision: "APPROVED" | "REJECTED", comment?: string) =>
      request<{ status: string; resolved_at: string }>(`/approvals/${approvalId}/resolve`, {
        method: "POST",
        body: JSON.stringify({ decision, comment }),
      }),
  },

  // Datasets
  datasets: {
    list: () => request<DatasetItem[]>("/datasets"),
    get: (id: string) => request<DatasetItem>(`/datasets/${id}`),
  },

  // Semantic Catalog & Graph
  semantic: {
    getTerms: () => request<SemanticTerm[]>("/semantic/terms"),
    getMetrics: () => request<SemanticMetric[]>("/semantic/metrics"),
    getGraph: (query?: string) =>
      request<{ nodes: unknown[]; edges: unknown[] }>(`/graph/explore?q=${encodeURIComponent(query || "")}`),
  },

  // Continuous Evaluation
  evaluation: {
    getScorecards: () => request<EvaluationScorecard[]>("/evaluation/scorecards"),
  },

  // Auth & Session
  auth: {
    me: () => request<User>("/auth/me"),
    login: (credentials: { username: string; password?: string }) =>
      request<User>("/auth/login", {
        method: "POST",
        body: JSON.stringify(credentials),
      }),
    logout: () =>
      request<{ success: boolean }>("/auth/logout", {
        method: "POST",
      }),
  },
};
