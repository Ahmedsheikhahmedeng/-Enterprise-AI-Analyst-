import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AnalystComposer } from "@/features/analyst/composer";

describe("AnalystComposer Component Tests", () => {
  it("renders composer textarea and mode selectors", () => {
    const handleSubmit = vi.fn();
    render(<AnalystComposer onSubmit={handleSubmit} isExecuting={false} />);

    expect(
      screen.getByPlaceholderText(/Ask a question about corporate financials/i)
    ).toBeInTheDocument();
    expect(screen.getByText("AUTO")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
    expect(screen.getByText("RAG")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /ask/i })).toBeInTheDocument();
  });

  it("submits question with selected mode when Ask button is clicked", () => {
    const handleSubmit = vi.fn();
    render(<AnalystComposer onSubmit={handleSubmit} isExecuting={false} />);

    const textarea = screen.getByPlaceholderText(/Ask a question about corporate financials/i);
    fireEvent.change(textarea, { target: { value: "What was Q3 revenue?" } });

    // Switch to SQL mode
    const sqlButton = screen.getByText("SQL");
    fireEvent.click(sqlButton);

    const askButton = screen.getByRole("button", { name: /ask/i });
    fireEvent.click(askButton);

    expect(handleSubmit).toHaveBeenCalledWith({
      question: "What was Q3 revenue?",
      mode: "SQL",
      responseStyle: "STANDARD",
      stream: true,
    });
  });

  it("renders Stop button when isExecuting is true and calls onStop", () => {
    const handleSubmit = vi.fn();
    const handleStop = vi.fn();
    render(
      <AnalystComposer
        onSubmit={handleSubmit}
        onStop={handleStop}
        isExecuting={true}
      />
    );

    const stopButton = screen.getByRole("button", { name: /stop/i });
    expect(stopButton).toBeInTheDocument();
    fireEvent.click(stopButton);
    expect(handleStop).toHaveBeenCalledTimes(1);
  });
});
