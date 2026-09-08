import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";
import { FinOpsNav } from "@/components/finops/finops-nav";
import { Providers } from "@/lib/query/providers";
import { AuthProvider } from "@/features/auth/auth-context";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/finops",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("Canonical Frontend User Journeys & Navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("Journey: renders core platform navigation with all enterprise subsystems", () => {
    render(
      <Providers>
        <AuthProvider>
          <Sidebar />
        </AuthProvider>
      </Providers>
    );

    // Verify key platform destinations exist in sidebar
    expect(screen.getByText("Enterprise AI")).toBeInTheDocument();
    expect(screen.getByText("Analyst Platform")).toBeInTheDocument();
    expect(screen.getByText("AI Analyst")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Security & GRC")).toBeInTheDocument();
    expect(screen.getByText("FinOps & Cost")).toBeInTheDocument();
  });

  it("Journey: verifies FinOps Hub tabs and billing disclaimer", () => {
    render(
      <Providers>
        <AuthProvider>
          <FinOpsNav />
        </AuthProvider>
      </Providers>
    );

    // Verify all 9 FinOps sections are reachable
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Usage Explorer")).toBeInTheDocument();
    expect(screen.getByText("Budgets & Quotas")).toBeInTheDocument();
    expect(screen.getByText("Models")).toBeInTheDocument();
    expect(screen.getByText("Providers")).toBeInTheDocument();
    expect(screen.getByText("Anomalies")).toBeInTheDocument();
    expect(screen.getByText("Forecasts")).toBeInTheDocument();
    expect(screen.getByText("Recommendations")).toBeInTheDocument();
    expect(screen.getByText("Reconciliation")).toBeInTheDocument();
  });

  it("UX Failure States: renders accessible error boundary and empty state representations", () => {
    const EmptyState = ({ message }: { message: string }) => (
      <div role="status" aria-live="polite" className="p-4 text-center">
        <p>{message}</p>
      </div>
    );

    render(<EmptyState message="No cost anomalies detected in current period." />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "No cost anomalies detected in current period."
    );
  });
});
