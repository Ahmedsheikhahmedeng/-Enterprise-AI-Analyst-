"use client";

import React, { useState } from "react";
import { EvidenceItem } from "@/types/platform";
import { Database, FileText, Share2, Layers, Search, ShieldCheck, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface EvidencePanelProps {
  evidence: EvidenceItem[];
  highlightedCitationId?: string | null;
  onClose?: () => void;
}

export function EvidencePanel({
  evidence,
  highlightedCitationId,
  onClose,
}: EvidencePanelProps) {
  const [filterType, setFilterType] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const getSourceIcon = (type: string) => {
    switch (type) {
      case "SQL_RECORD":
        return <Database className="h-3.5 w-3.5 text-sky-500" />;
      case "VECTOR_CHUNK":
        return <FileText className="h-3.5 w-3.5 text-emerald-500" />;
      case "GRAPH_EDGE":
        return <Share2 className="h-3.5 w-3.5 text-indigo-500" />;
      case "SEMANTIC_METRIC":
        return <Layers className="h-3.5 w-3.5 text-amber-500" />;
      default:
        return <FileText className="h-3.5 w-3.5 text-muted-foreground" />;
    }
  };

  const filteredEvidence = evidence.filter((item) => {
    const matchesType = filterType === "ALL" || item.source_type === filterType;
    const matchesSearch =
      searchQuery === "" ||
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.snippet.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  return (
    <div className="flex h-full flex-col border-l border-border bg-card/50 backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/80 px-4 py-3">
        <div className="flex items-center gap-2">
          <Layers className="h-4 w-4 text-primary" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
            Verified Evidence ({evidence.length})
          </h3>
        </div>
        {onClose && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="h-7 w-7 text-muted-foreground"
            aria-label="Close evidence panel"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {/* Search & Filters */}
      <div className="p-3 border-b border-border/60 space-y-2">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter evidence records..."
            className="h-8 pl-8 text-xs bg-background"
          />
        </div>
        <div className="flex gap-1 overflow-x-auto pb-1 text-[10px]">
          {["ALL", "SQL_RECORD", "VECTOR_CHUNK", "GRAPH_EDGE", "SEMANTIC_METRIC"].map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`rounded px-2 py-0.5 font-medium whitespace-nowrap transition-colors ${
                filterType === type
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "bg-muted/80 text-muted-foreground hover:bg-muted"
              }`}
            >
              {type === "ALL" ? "All Sources" : type.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Evidence Items List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {filteredEvidence.length === 0 ? (
          <div className="p-8 text-center text-xs text-muted-foreground">
            No evidence matches the current filters.
          </div>
        ) : (
          filteredEvidence.map((item, idx) => {
            const isHighlighted =
              highlightedCitationId &&
              item.id.toLowerCase().includes(highlightedCitationId.toLowerCase().replace(/[[\]]/g, ""));

            return (
              <div
                key={item.id || idx}
                id={`evidence-${item.id}`}
                className={`rounded-lg border p-3 text-xs transition-all ${
                  isHighlighted
                    ? "border-primary bg-primary/10 shadow-md ring-1 ring-primary"
                    : "border-border/80 bg-card hover:border-border"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5 font-mono text-[11px] font-semibold text-foreground">
                    {getSourceIcon(item.source_type)}
                    <span className="truncate max-w-[160px]">{item.title}</span>
                  </div>
                  {item.trust_level && (
                    <span className="flex items-center gap-1 text-[10px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                      <ShieldCheck className="h-2.5 w-2.5" />
                      {item.trust_level}
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-muted-foreground leading-relaxed bg-muted/30 p-2 rounded font-mono break-words">
                  {item.snippet}
                </p>

                <div className="flex items-center justify-between mt-2 pt-1 border-t border-border/40 text-[10px] text-muted-foreground">
                  <span>Score: {item.score ? `${Math.round(item.score * 100)}%` : "Verified"}</span>
                  {item.source_uri && (
                    <span className="truncate max-w-[120px]" title={item.source_uri}>
                      {item.source_uri}
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
