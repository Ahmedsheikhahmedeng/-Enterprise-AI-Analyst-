"use client";

import React from "react";
import Link from "next/link";
import { GraphViewer } from "@/features/semantic/graph-viewer";
import { ArrowLeft, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function GraphPage() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/semantic">
          <Button variant="outline" size="sm" className="h-8 gap-1 text-xs">
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Semantic Layer</span>
          </Button>
        </Link>
      </div>

      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-500">
          <Share2 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            Knowledge Graph Exploration
          </h1>
          <p className="text-xs text-muted-foreground">
            Multi-hop relational pathways, entity neighbors, and domain lineage.
          </p>
        </div>
      </div>

      <GraphViewer />
    </div>
  );
}
