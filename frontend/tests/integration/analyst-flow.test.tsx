import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AnalystWorkspace } from "@/features/analyst/workspace";
import { Providers } from "@/lib/query/providers";
import { AuthProvider } from "@/features/auth/auth-context";
import { apiClient } from "@/lib/api/client";

vi.mock("@/lib/api/client", () => ({
  apiClient: {
    ask: {
      submit: vi.fn(),
      cancel: vi.fn(),
      getReplayEvents: vi.fn(),
    },
    auth: {
      me: vi.fn().mockResolvedValue({ data: null }),
      login: vi.fn(),
      logout: vi.fn(),
    },
  },
}));

describe("Analyst Workspace Integration Flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders workspace layout with history, composer, and initial state", () => {
    render(
      <Providers>
        <AuthProvider>
          <AnalystWorkspace />
        </AuthProvider>
      </Providers>
    );

    expect(screen.getByText("Workspace Analysis")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/Ask a question about corporate financials/i)).toBeInTheDocument();
    expect(screen.getByText("Q3 Enterprise Financial Performance")).toBeInTheDocument();
  });

  it("handles ask submission and updates answer with citations", async () => {
    const mockPayload = {
      execution_id: "test-exec-456",
      status: "COMPLETED" as const,
      question: "What is the ARR?",
      mode: "AUTO" as const,
      answer: "The ARR for Q3 is $84.2M [S1].",
      evidence: [
        {
          id: "S1",
          source_type: "SQL_RECORD" as const,
          title: "contracts_table.arr",
          snippet: "SUM(arr) = 84.2M",
          score: 0.99,
          trust_level: "DIRECT_DB",
        },
      ],
      citations: [
        {
          citation_id: "[S1]",
          source_type: "SQL_RECORD" as const,
          title: "contracts_table.arr",
          snippet: "SUM(arr) = 84.2M",
          confidence: 0.99,
          trust_level: "DIRECT_DB",
        },
      ],
      confidence_score: 0.98,
      stage_progress: {},
      is_partial: false,
      has_conflicts: false,
      clarification_needed: false,
      created_at: new Date().toISOString(),
    };

    (apiClient.ask.submit as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      data: mockPayload,
    });

    render(
      <Providers>
        <AuthProvider>
          <AnalystWorkspace />
        </AuthProvider>
      </Providers>
    );

    const textarea = screen.getByPlaceholderText(/Ask a question about corporate financials/i);
    fireEvent.change(textarea, { target: { value: "What is the ARR?" } });

    const askButton = screen.getByRole("button", { name: /ask/i });
    fireEvent.click(askButton);

    await waitFor(() => {
      expect(apiClient.ask.submit).toHaveBeenCalledWith({
        question: "What is the ARR?",
        mode: "AUTO",
        response_style: "STANDARD",
        stream: true,
        conversation_id: "conv-1",
      });
    });

    await waitFor(() => {
      expect(screen.getByText(/The ARR for Q3 is \$84\.2M/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Citation \[S1\]/i })).toBeInTheDocument();
    });
  });

  it("opens evidence panel when citation is clicked", async () => {
    render(
      <Providers>
        <AuthProvider>
          <AnalystWorkspace />
        </AuthProvider>
      </Providers>
    );

    // Initial answer has [S1]
    const citationBadge = screen.getByRole("button", { name: /Citation \[S1\]/i });
    expect(citationBadge).toBeInTheDocument();

    fireEvent.click(citationBadge);

    // Evidence panel should open
    await waitFor(() => {
      expect(screen.getByText(/Verified Evidence/i)).toBeInTheDocument();
    });
  });
});
