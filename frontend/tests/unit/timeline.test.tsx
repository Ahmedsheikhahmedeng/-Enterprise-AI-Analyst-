import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ExecutionTimeline, EXECUTION_STAGES } from "@/features/analyst/timeline";

describe("ExecutionTimeline Component Tests", () => {
  it("renders all 8 execution stages", () => {
    render(
      <ExecutionTimeline
        currentStage="PLANNING"
        completedStages={["UNDERSTANDING", "SEMANTIC", "GRAPH"]}
        progressPercent={40}
      />
    );

    for (const stage of EXECUTION_STAGES) {
      expect(screen.getByText(stage.label)).toBeInTheDocument();
    }
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("displays completed state when isCompleted is true", () => {
    render(
      <ExecutionTimeline
        currentStage="RESPONSE"
        completedStages={EXECUTION_STAGES.map((s) => s.name)}
        progressPercent={100}
        isCompleted={true}
      />
    );

    expect(screen.getByText("Execution Completed")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("displays failed state when isFailed is true", () => {
    render(
      <ExecutionTimeline
        currentStage="EXECUTION"
        completedStages={["UNDERSTANDING"]}
        progressPercent={25}
        isFailed={true}
      />
    );

    expect(screen.getByText("Execution Failed")).toBeInTheDocument();
  });
});
