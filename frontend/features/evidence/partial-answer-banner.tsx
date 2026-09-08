"use client";

import React from "react";
import { Info } from "lucide-react";

export function PartialAnswerBanner() {
  return (
    <div className="rounded-lg border border-sky-500/30 bg-sky-500/10 p-3 my-3 text-sky-900 dark:text-sky-200">
      <div className="flex items-start gap-2.5">
        <Info className="h-4 w-4 shrink-0 text-sky-600 dark:text-sky-400 mt-0.5" />
        <div className="space-y-0.5">
          <h4 className="text-xs font-semibold tracking-tight">Partial Answer Generated</h4>
          <p className="text-[11px] leading-relaxed text-sky-800 dark:text-sky-300">
            Portions of the requested data could not be retrieved due to source availability or governance boundaries. Verified segments are presented below.
          </p>
        </div>
      </div>
    </div>
  );
}
