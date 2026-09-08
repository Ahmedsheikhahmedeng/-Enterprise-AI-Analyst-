"use client";

import React from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { ShieldCheck, AlertCircle, Info } from "lucide-react";

interface ConfidenceBadgeProps {
  score?: number | null;
  hasConflicts?: boolean;
}

export function ConfidenceBadge({ score, hasConflicts }: ConfidenceBadgeProps) {
  if (score == null) return null;

  const percentage = Math.round(score * 100);

  let variant: "high" | "medium" | "low" = "high";
  let label = "High Confidence";
  let colorClasses = "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20";
  let Icon = ShieldCheck;

  if (hasConflicts || score < 0.7) {
    variant = "low";
    label = hasConflicts ? "Conflict Detected" : "Low Confidence";
    colorClasses = "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20";
    Icon = AlertCircle;
  } else if (score < 0.85) {
    variant = "medium";
    label = "Moderate Confidence";
    colorClasses = "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20";
    Icon = Info;
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium cursor-help transition-all ${colorClasses}`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span>{label}</span>
            <span className="font-mono font-bold">({percentage}%)</span>
          </div>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs p-3 space-y-1.5 text-xs">
          <div className="font-semibold text-foreground border-b border-border pb-1">
            Confidence Evaluation
          </div>
          <p className="text-muted-foreground text-[11px] leading-relaxed">
            Derived from verified evidence coverage across structured SQL, verified semantic catalog definitions, and ground-truth citations.
          </p>
          <div className="pt-1 text-[10px] text-muted-foreground space-y-0.5">
            <div>• Evidence coverage: {variant === "high" ? "Exhaustive" : "Partial"}</div>
            <div>• Source credibility: High (Direct DB / Vector)</div>
            <div>• Conflict status: {hasConflicts ? "Contradictions found" : "Consistent"}</div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
