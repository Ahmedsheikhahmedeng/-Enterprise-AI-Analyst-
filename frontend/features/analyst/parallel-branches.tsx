"use client";

import React from "react";
import { Database, FileText, Share2 } from "lucide-react";

interface BranchStatus {
  name: "SQL" | "RAG" | "GRAPH";
  progress: number; // 0 - 100
  status: "ACTIVE" | "COMPLETED" | "PENDING";
  itemCount?: number;
}

interface ParallelBranchesProps {
  branches?: BranchStatus[];
}

export function ParallelBranches({
  branches = [
    { name: "SQL", progress: 85, status: "ACTIVE", itemCount: 14 },
    { name: "RAG", progress: 65, status: "ACTIVE", itemCount: 6 },
    { name: "GRAPH", progress: 40, status: "ACTIVE", itemCount: 3 },
  ],
}: ParallelBranchesProps) {
  const getBranchIcon = (name: string) => {
    switch (name) {
      case "SQL":
        return <Database className="h-3 w-3 text-sky-500" />;
      case "RAG":
        return <FileText className="h-3 w-3 text-emerald-500" />;
      case "GRAPH":
        return <Share2 className="h-3 w-3 text-indigo-500" />;
    }
  };

  return (
    <div className="rounded-xl border border-border/80 bg-card/40 p-3 space-y-2.5 backdrop-blur-xs">
      <div className="flex items-center justify-between text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
        <span>Concurrent Hybrid Branches</span>
        <span className="text-[10px] lowercase font-normal text-primary">Parallel Execution</span>
      </div>

      <div className="space-y-2">
        {branches.map((b) => (
          <div key={b.name} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 font-semibold text-foreground">
                {getBranchIcon(b.name)}
                <span>{b.name} Branch</span>
              </div>
              <span className="text-[11px] font-mono text-muted-foreground">
                {b.itemCount != null ? `${b.itemCount} items • ` : ""}{b.progress}%
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className="h-full bg-primary/80 transition-all duration-300 rounded-full"
                style={{ width: `${b.progress}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
