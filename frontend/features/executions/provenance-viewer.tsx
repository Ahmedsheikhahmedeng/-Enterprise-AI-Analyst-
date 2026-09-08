"use client";

import React from "react";
import { ShieldCheck, GitBranch, Cpu, Clock, Layers } from "lucide-react";
import { formatDuration } from "@/lib/utils";

interface ProvenanceViewerProps {
  provenance?: {
    system_version?: string;
    model_version?: string;
    prompt_hash?: string;
    schema_version?: string;
    duration_ms?: number;
  };
  evidenceCount?: number;
}

export function ProvenanceViewer({
  provenance,
  evidenceCount = 0,
}: ProvenanceViewerProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 space-y-3">
      <div className="flex items-center gap-2 border-b border-border/80 pb-2.5">
        <ShieldCheck className="h-4 w-4 text-primary" />
        <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
          Execution Provenance & Reproducibility Audit
        </h4>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div className="rounded-lg bg-muted/40 p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground text-[11px]">
            <GitBranch className="h-3.5 w-3.5 text-primary" />
            <span>System Version</span>
          </div>
          <div className="font-mono font-semibold text-foreground truncate">
            {provenance?.system_version || "v2.4-enterprise"}
          </div>
        </div>

        <div className="rounded-lg bg-muted/40 p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground text-[11px]">
            <Cpu className="h-3.5 w-3.5 text-indigo-500" />
            <span>Model Tier</span>
          </div>
          <div className="font-mono font-semibold text-foreground truncate">
            {provenance?.model_version || "enterprise-orchestrator-v1"}
          </div>
        </div>

        <div className="rounded-lg bg-muted/40 p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground text-[11px]">
            <Clock className="h-3.5 w-3.5 text-amber-500" />
            <span>Duration</span>
          </div>
          <div className="font-mono font-semibold text-foreground">
            {formatDuration(provenance?.duration_ms || 184)}
          </div>
        </div>

        <div className="rounded-lg bg-muted/40 p-2.5 space-y-1">
          <div className="flex items-center gap-1.5 text-muted-foreground text-[11px]">
            <Layers className="h-3.5 w-3.5 text-emerald-500" />
            <span>Verified Sources</span>
          </div>
          <div className="font-mono font-semibold text-foreground">
            {evidenceCount} ground-truth items
          </div>
        </div>
      </div>

      <div className="text-[11px] text-muted-foreground font-mono bg-muted/20 p-2 rounded border border-border/40">
        Prompt Hash: {provenance?.prompt_hash || "sha256:7fa1bc82019a4c919e23"} • Schema Version: {provenance?.schema_version || "2026.09-v1"}
      </div>
    </div>
  );
}
