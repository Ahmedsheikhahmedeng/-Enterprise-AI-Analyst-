import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MarkdownRenderer } from "@/components/common/markdown-renderer";
import { Citation } from "@/types/platform";

const SAMPLE_CITATIONS: Citation[] = [
  {
    citation_id: "[S1]",
    source_type: "SQL_RECORD",
    title: "q3_revenue_ledger",
    snippet: "Total net revenue reached $142.8M USD",
    trust_level: "DIRECT_DB",
    confidence: 0.99,
  },
];

describe("MarkdownRenderer Component Tests", () => {
  it("renders markdown headings, paragraphs, and lists", () => {
    const markdown = "### Revenue Summary\n\nTotal revenue expanded by 18%.\n\n- Cloud: $84M\n- Data: $38M";
    render(<MarkdownRenderer content={markdown} />);

    expect(screen.getByText("Revenue Summary")).toBeInTheDocument();
    expect(screen.getByText("Total revenue expanded by 18%.")).toBeInTheDocument();
    expect(screen.getByText("Cloud: $84M")).toBeInTheDocument();
  });

  it("detects and renders citation badges with click handler", () => {
    const markdown = "Q3 total revenue reached $142.8M [S1].";
    const handleCitationClick = vi.fn();

    render(
      <MarkdownRenderer
        content={markdown}
        citations={SAMPLE_CITATIONS}
        onCitationClick={handleCitationClick}
      />
    );

    const badge = screen.getByRole("button", { name: /Citation \[S1\]/i });
    expect(badge).toBeInTheDocument();

    fireEvent.click(badge);
    expect(handleCitationClick).toHaveBeenCalledWith("[S1]");
  });

  it("renders structured markdown tables", () => {
    const tableMarkdown = "| Metric | Value |\n|---|---|\n| Revenue | $142.8M |\n| Net Income | $34.6M |";
    render(<MarkdownRenderer content={tableMarkdown} />);

    expect(screen.getByText("Metric")).toBeInTheDocument();
    expect(screen.getByText("Value")).toBeInTheDocument();
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("$142.8M")).toBeInTheDocument();
  });
});
