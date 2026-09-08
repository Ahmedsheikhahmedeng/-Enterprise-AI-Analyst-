"use client";

import React, { useState } from "react";
import { Share2, Search, ShieldCheck } from "lucide-react";
import { Input } from "@/components/ui/input";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  neighborCount: number;
}

interface GraphEdge {
  source: string;
  target: string;
  relation: string;
}

const SAMPLE_NODES: GraphNode[] = [
  { id: "ent-1", name: "Corporate Customer Account", type: "ENTITY", neighborCount: 4 },
  { id: "ent-2", name: "Sales Subscription Contract", type: "CONTRACT", neighborCount: 3 },
  { id: "ent-3", name: "Invoice Ledger Record", type: "TRANSACTION", neighborCount: 5 },
  { id: "ent-4", name: "Recognized ARR Metric", type: "METRIC", neighborCount: 2 },
];

const SAMPLE_EDGES: GraphEdge[] = [
  { source: "Corporate Customer Account", target: "Sales Subscription Contract", relation: "HOLDS_CONTRACT" },
  { source: "Sales Subscription Contract", target: "Invoice Ledger Record", relation: "GENERATES_INVOICE" },
  { source: "Invoice Ledger Record", target: "Recognized ARR Metric", relation: "AGGREGATES_INTO" },
];

export function GraphViewer() {
  const [search, setSearch] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode>(SAMPLE_NODES[0]);

  const filteredNodes = SAMPLE_NODES.filter((n) =>
    n.name.toLowerCase().includes(search.toLowerCase())
  );

  const relatedEdges = SAMPLE_EDGES.filter(
    (e) => e.source === selectedNode.name || e.target === selectedNode.name
  );

  return (
    <div className="space-y-4">
      {/* Search Header */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search graph entities..."
          className="h-8 pl-8 text-xs bg-card"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Nodes List */}
        <div className="rounded-xl border border-border bg-card p-4 space-y-2">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
            Entities & Concepts ({filteredNodes.length})
          </h4>
          <div className="space-y-1.5">
            {filteredNodes.map((node) => (
              <button
                key={node.id}
                onClick={() => setSelectedNode(node)}
                className={`flex w-full items-center justify-between rounded-lg p-2.5 text-xs text-left transition-colors ${
                  selectedNode.id === node.id
                    ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <Share2 className="h-3.5 w-3.5 shrink-0 opacity-70" />
                  <span className="truncate">{node.name}</span>
                </div>
                <span className="text-[10px] font-mono opacity-70">
                  {node.neighborCount} rels
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* Selected Entity Details & Lineage */}
        <div className="md:col-span-2 rounded-xl border border-border bg-card p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between border-b border-border/70 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-bold text-foreground">
                  {selectedNode.name}
                </h3>
                <span className="rounded bg-indigo-500/10 px-2 py-0.5 font-mono text-[10px] font-bold text-indigo-500">
                  {selectedNode.type}
                </span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                Knowledge Graph Semantic Relationships & Lineage
              </span>
            </div>

            <span className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400">
              <ShieldCheck className="h-3.5 w-3.5" />
              <span>Verified Entity</span>
            </span>
          </div>

          <div className="space-y-2.5">
            <h5 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Connected Neighbor Edges ({relatedEdges.length})
            </h5>
            {relatedEdges.map((edge, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-lg bg-muted/40 p-3 text-xs border border-border/50"
              >
                <span className="font-semibold text-foreground">{edge.source}</span>
                <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-[10px] font-mono font-bold text-primary">
                  {edge.relation}
                </span>
                <span className="font-semibold text-foreground">{edge.target}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
