import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EvidencePanel } from "@/features/evidence/evidence-panel";
import { EvidenceItem } from "@/types/platform";

const SAMPLE_EVIDENCE: EvidenceItem[] = [
  {
    id: "S1",
    source_type: "SQL_RECORD",
    title: "financial_ledger_revenue",
    snippet: "SELECT SUM(net_revenue) -> 142.8M USD",
    score: 0.99,
    trust_level: "DIRECT_DB",
  },
  {
    id: "D1",
    source_type: "VECTOR_CHUNK",
    title: "sec_q3_report.pdf",
    snippet: "Operating expenses decreased by 4.2%",
    score: 0.95,
    trust_level: "VERIFIED_DOC",
  },
];

describe("EvidencePanel Component Tests", () => {
  it("renders evidence items count and titles", () => {
    render(<EvidencePanel evidence={SAMPLE_EVIDENCE} />);

    expect(screen.getByText(/Verified Evidence \(2\)/i)).toBeInTheDocument();
    expect(screen.getByText("financial_ledger_revenue")).toBeInTheDocument();
    expect(screen.getByText("sec_q3_report.pdf")).toBeInTheDocument();
  });

  it("filters evidence by search query", () => {
    render(<EvidencePanel evidence={SAMPLE_EVIDENCE} />);

    const searchInput = screen.getByPlaceholderText(/Filter evidence records/i);
    fireEvent.change(searchInput, { target: { value: "Operating expenses" } });

    expect(screen.queryByText("financial_ledger_revenue")).not.toBeInTheDocument();
    expect(screen.getByText("sec_q3_report.pdf")).toBeInTheDocument();
  });
});
