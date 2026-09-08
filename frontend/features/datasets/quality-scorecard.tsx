"use client";

import React from "react";
import { formatPercent } from "@/lib/utils";
import { CheckCircle2, AlertTriangle } from "lucide-react";

interface QualityScorecardProps {
  qualityScore?: number;
  nullRatio?: number;
  duplicateRatio?: number;
  invalidRatio?: number;
}

export function QualityScorecard({
  qualityScore = 0.98,
  nullRatio = 0.01,
  duplicateRatio = 0.0,
  invalidRatio = 0.005,
}: QualityScorecardProps) {
  const isHealthy = qualityScore >= 0.9;

  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-4 shadow-xs">
      <div className="flex items-center justify-between border-b border-border/70 pb-3">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
            Dataset Quality & Integrity Health
          </h4>
          <span className="text-[11px] text-muted-foreground">
            Automated schema validation & profiling results
          </span>
        </div>

        <div
          className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
            isHealthy
              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
              : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
          }`}
        >
          {isHealthy ? (
            <CheckCircle2 className="h-3.5 w-3.5" />
          ) : (
            <AlertTriangle className="h-3.5 w-3.5" />
          )}
          <span>Score: {formatPercent(qualityScore)}</span>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-lg bg-muted/40 p-3">
          <span className="text-[11px] text-muted-foreground">Null Ratio</span>
          <div className="text-base font-bold text-foreground font-mono mt-0.5">
            {formatPercent(nullRatio)}
          </div>
        </div>

        <div className="rounded-lg bg-muted/40 p-3">
          <span className="text-[11px] text-muted-foreground">Duplicate Ratio</span>
          <div className="text-base font-bold text-foreground font-mono mt-0.5">
            {formatPercent(duplicateRatio)}
          </div>
        </div>

        <div className="rounded-lg bg-muted/40 p-3">
          <span className="text-[11px] text-muted-foreground">Invalid Schema Ratio</span>
          <div className="text-base font-bold text-foreground font-mono mt-0.5">
            {formatPercent(invalidRatio)}
          </div>
        </div>
      </div>
    </div>
  );
}
