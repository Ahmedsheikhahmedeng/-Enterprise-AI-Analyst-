"use client";

import React, { use } from "react";
import Link from "next/link";
import { ProvenanceViewer } from "@/features/executions/provenance-viewer";
import { MarkdownRenderer } from "@/components/common/markdown-renderer";
import { ArrowLeft, CheckCircle2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ExecutionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const id = resolvedParams.id;

  const sampleExecution = {
    execution_id: id,
    question: "What are Q3 financial earnings results and operating margins?",
    status: "COMPLETED",
    mode: "AUTO",
    duration_ms: 184.2,
    created_at: new Date().toISOString(),
    answer: "In Q3 2026, total consolidated net revenue reached **$142.8M** [S1], representing an **18.4% year-over-year increase** compared to Q3 2025 ($120.6M) [D1].\n\nOperating income expanded to **$34.6M** [S2], driven primarily by efficiency gains in infrastructure routing.",
    citations: [
      {
        citation_id: "[S1]",
        source_type: "SQL_RECORD" as const,
        title: "financial_ledger_q3_2026.revenue",
        snippet: "SELECT SUM(net_revenue) FROM enterprise_ledgers WHERE fiscal_year = 2026 AND quarter = 'Q3' -> 142,800,000.00 USD",
        trust_level: "DIRECT_DB",
        confidence: 0.99,
      },
      {
        citation_id: "[S2]",
        source_type: "SQL_RECORD" as const,
        title: "operating_expenses_q3_summary",
        snippet: "SELECT operating_income FROM quarterly_financial_statements WHERE quarter = '2026-Q3' -> 34,600,000.00 USD",
        trust_level: "DIRECT_DB",
        confidence: 0.98,
      },
      {
        citation_id: "[D1]",
        source_type: "VECTOR_CHUNK" as const,
        title: "Q3_2025_Shareholder_Letter.pdf",
        snippet: "Consolidated quarterly net revenue for the third quarter ending September 30, 2025 was recorded at $120.6 million.",
        trust_level: "VERIFIED_DOC",
        confidence: 0.94,
      },
    ],
    provenance: {
      system_version: "v2.4-enterprise",
      model_version: "enterprise-orchestrator-v1",
      prompt_hash: "sha256:7fa1bc82019a4c919e23",
      schema_version: "2026.09-v1",
      duration_ms: 184.2,
    },
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      {/* Top Navigation */}
      <div className="flex items-center gap-3">
        <Link href="/executions">
          <Button variant="outline" size="sm" className="h-8 gap-1 text-xs">
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Executions</span>
          </Button>
        </Link>
        <span className="text-xs font-mono text-muted-foreground truncate">
          Execution ID: {id}
        </span>
      </div>

      {/* Header Info */}
      <div className="rounded-xl border border-border bg-card p-6 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 pb-3">
          <div className="space-y-1">
            <span className="text-[11px] font-mono text-muted-foreground uppercase tracking-wider">
              Question Prompt
            </span>
            <h2 className="text-base font-bold text-foreground">
              {sampleExecution.question}
            </h2>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded bg-muted px-2.5 py-1 font-mono text-xs font-semibold text-foreground">
              Mode: {sampleExecution.mode}
            </span>
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {sampleExecution.status}
            </span>
          </div>
        </div>

        {/* Answer Content */}
        <div className="space-y-2 pt-2">
          <div className="flex items-center gap-2 text-xs font-semibold text-primary">
            <Sparkles className="h-4 w-4" />
            <span>Generated Verified Response</span>
          </div>
          <div className="rounded-lg bg-muted/20 border border-border/60 p-4">
            <MarkdownRenderer
              content={sampleExecution.answer}
              citations={sampleExecution.citations}
            />
          </div>
        </div>
      </div>

      {/* Provenance Viewer */}
      <ProvenanceViewer
        provenance={sampleExecution.provenance}
        evidenceCount={sampleExecution.citations.length}
      />
    </div>
  );
}
