"use client";

import React from "react";
import { HelpCircle } from "lucide-react";

export function InsufficientEvidenceBanner() {
  return (
    <div className="rounded-lg border border-border bg-muted/50 p-4 my-3 text-foreground">
      <div className="flex items-start gap-3">
        <HelpCircle className="h-5 w-5 shrink-0 text-muted-foreground mt-0.5" />
        <div className="space-y-1">
          <h4 className="text-xs font-semibold tracking-tight">Insufficient Verified Evidence</h4>
          <p className="text-xs text-muted-foreground leading-relaxed">
            The platform did not find sufficient authoritative evidence in enterprise databases, indexed documents, or semantic definitions to reliably synthesize a factual response.
          </p>
        </div>
      </div>
    </div>
  );
}
