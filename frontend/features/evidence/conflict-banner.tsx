"use client";

import React from "react";
import { AlertTriangle } from "lucide-react";

export function ConflictBanner() {
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3.5 my-3 text-amber-900 dark:text-amber-200">
      <div className="flex items-start gap-2.5">
        <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
        <div className="space-y-1">
          <h4 className="text-xs font-semibold tracking-tight">
            Conflicting Evidence Detected Across Sources
          </h4>
          <p className="text-[11px] leading-relaxed text-amber-800 dark:text-amber-300">
            The platform identified contradictory data points between primary operational databases and secondary documents. Both claims are documented below; authoritative consensus could not be established.
          </p>
        </div>
      </div>
    </div>
  );
}
