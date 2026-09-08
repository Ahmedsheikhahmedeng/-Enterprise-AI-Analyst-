"use client";

import React from "react";
import { CheckCircle2, Loader2, Circle } from "lucide-react";

export interface StageInfo {
  name: string;
  label: string;
  weight: number;
}

export const EXECUTION_STAGES: StageInfo[] = [
  { name: "UNDERSTANDING", label: "Understanding", weight: 10 },
  { name: "SEMANTIC", label: "Semantic Resolution", weight: 20 },
  { name: "GRAPH", label: "Graph Reasoning", weight: 30 },
  { name: "PLANNING", label: "Planning", weight: 40 },
  { name: "EXECUTION", label: "Execution (SQL/RAG)", weight: 65 },
  { name: "EVIDENCE", label: "Evidence Collection", weight: 80 },
  { name: "VERIFICATION", label: "Verification & Governance", weight: 90 },
  { name: "RESPONSE", label: "Final Response", weight: 100 },
];

interface ExecutionTimelineProps {
  currentStage: string;
  completedStages: string[];
  progressPercent: number;
  isCompleted?: boolean;
  isFailed?: boolean;
}

export function ExecutionTimeline({
  currentStage,
  completedStages,
  progressPercent,
  isCompleted = false,
  isFailed = false,
}: ExecutionTimelineProps) {
  return (
    <div className="rounded-xl border border-border/70 bg-card/60 p-4 space-y-3 backdrop-blur-xs">
      {/* Header & Progress Bar */}
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-foreground">
          {isCompleted
            ? "Execution Completed"
            : isFailed
            ? "Execution Failed"
            : "Orchestration Pipeline"}
        </span>
        <span className="font-mono font-bold text-primary">
          {Math.min(100, Math.max(0, Math.round(progressPercent)))}%
        </span>
      </div>

      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full transition-all duration-500 ease-out ${
            isFailed
              ? "bg-destructive"
              : isCompleted
              ? "bg-emerald-500"
              : "bg-primary"
          }`}
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Stage Items Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
        {EXECUTION_STAGES.map((stage) => {
          const isDone = isCompleted || completedStages.includes(stage.name);
          const isActive = !isCompleted && !isFailed && currentStage === stage.name;

          return (
            <div
              key={stage.name}
              className={`flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-medium transition-colors ${
                isDone
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : isActive
                  ? "bg-primary/10 text-primary font-semibold ring-1 ring-primary/30"
                  : "text-muted-foreground/60"
              }`}
            >
              {isDone ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
              ) : isActive ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-primary shrink-0" />
              ) : (
                <Circle className="h-3 w-3 shrink-0 opacity-40" />
              )}
              <span className="truncate">{stage.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
