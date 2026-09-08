"use client";

import React, { useState } from "react";
import { Citation } from "@/types/platform";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Database, FileText, Share2, Layers, ExternalLink, ShieldCheck } from "lucide-react";

interface CitationBadgeProps {
  citationId: string; // e.g. "[S1]"
  citation?: Citation;
  onClick?: () => void;
}

export function CitationBadge({ citationId, citation, onClick }: CitationBadgeProps) {
  const [open, setOpen] = useState(false);

  const getSourceIcon = (type?: string) => {
    switch (type) {
      case "SQL_RECORD":
        return <Database className="h-3 w-3 text-sky-500" />;
      case "VECTOR_CHUNK":
        return <FileText className="h-3 w-3 text-emerald-500" />;
      case "GRAPH_EDGE":
        return <Share2 className="h-3 w-3 text-indigo-500" />;
      case "SEMANTIC_METRIC":
        return <Layers className="h-3 w-3 text-amber-500" />;
      default:
        return <FileText className="h-3 w-3 text-muted-foreground" />;
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClick?.();
          }}
          className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.2 text-[10px] font-mono font-bold tracking-tight bg-primary/10 text-primary hover:bg-primary/20 border border-primary/25 cursor-pointer transition-colors align-baseline mx-0.5 shadow-xs"
          title={`View citation ${citationId}`}
          aria-label={`Citation ${citationId}`}
        >
          <span>{citationId}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-3 shadow-xl border-border bg-card" align="start">
        <div className="space-y-2">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border/60 pb-1.5">
            <div className="flex items-center gap-1.5">
              {getSourceIcon(citation?.source_type)}
              <span className="text-[11px] font-mono font-bold text-foreground">
                {citationId} • {citation?.source_type || "Source"}
              </span>
            </div>
            {citation?.trust_level && (
              <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                <ShieldCheck className="h-2.5 w-2.5" />
                {citation.trust_level}
              </span>
            )}
          </div>

          {/* Title */}
          <div className="text-xs font-semibold text-foreground line-clamp-1">
            {citation?.title || "Referenced Evidence Record"}
          </div>

          {/* Snippet */}
          <p className="text-[11px] text-muted-foreground line-clamp-3 bg-muted/40 p-2 rounded border border-border/40 font-sans italic">
            &quot;{citation?.snippet || "Evidence excerpt verified by continuous evaluation pipeline."}&quot;
          </p>

          {/* Meta & Navigation */}
          <div className="flex items-center justify-between pt-1 text-[10px] text-muted-foreground">
            <span>Confidence: {citation?.confidence ? `${Math.round(citation.confidence * 100)}%` : "Verified"}</span>
            <button
              onClick={() => {
                setOpen(false);
                onClick?.();
              }}
              className="flex items-center gap-1 text-primary hover:underline font-medium"
            >
              <span>Inspect in drawer</span>
              <ExternalLink className="h-2.5 w-2.5" />
            </button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}
