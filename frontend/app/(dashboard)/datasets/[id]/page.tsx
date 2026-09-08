"use client";

import React, { use } from "react";
import Link from "next/link";
import { QualityScorecard } from "@/features/datasets/quality-scorecard";
import { ArrowLeft, Database, CheckCircle2, Table } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function DatasetDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const id = resolvedParams.id;

  const sampleDataset = {
    id,
    name: "financial_general_ledgers",
    source_type: "POSTGRESQL",
    status: "SYNCED",
    row_count: 1420500,
    column_count: 24,
    quality_score: 0.99,
    null_ratio: 0.002,
    duplicate_ratio: 0.0,
    invalid_ratio: 0.001,
    schema: [
      { name: "id", type: "UUID", nullable: false, pk: true },
      { name: "fiscal_year", type: "INTEGER", nullable: false },
      { name: "quarter", type: "VARCHAR(4)", nullable: false },
      { name: "net_revenue", type: "NUMERIC(18,2)", nullable: false },
      { name: "operating_expenses", type: "NUMERIC(18,2)", nullable: false },
      { name: "currency", type: "VARCHAR(3)", nullable: false },
      { name: "created_at", type: "TIMESTAMP", nullable: false },
    ],
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/datasets">
          <Button variant="outline" size="sm" className="h-8 gap-1 text-xs">
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Back to Datasets</span>
          </Button>
        </Link>
        <span className="text-xs font-mono text-muted-foreground truncate">
          Dataset ID: {id}
        </span>
      </div>

      <div className="rounded-xl border border-border bg-card p-6 space-y-3">
        <div className="flex items-center justify-between border-b border-border/80 pb-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/10 text-sky-500">
              <Database className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-foreground">
                {sampleDataset.name}
              </h2>
              <span className="text-xs text-muted-foreground">
                Operational Relational Schema • {sampleDataset.source_type}
              </span>
            </div>
          </div>

          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {sampleDataset.status}
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-1">
          <div>Total Rows: <span className="font-mono font-semibold">{sampleDataset.row_count.toLocaleString()}</span></div>
          <div>Columns: <span className="font-mono font-semibold">{sampleDataset.column_count}</span></div>
          <div>Classification: <span className="font-mono font-semibold text-amber-500">FINANCIAL_CONFIDENTIAL</span></div>
          <div>Encryption: <span className="font-mono font-semibold text-emerald-600">AES-256-GCM</span></div>
        </div>
      </div>

      <QualityScorecard
        qualityScore={sampleDataset.quality_score}
        nullRatio={sampleDataset.null_ratio}
        duplicateRatio={sampleDataset.duplicate_ratio}
        invalidRatio={sampleDataset.invalid_ratio}
      />

      {/* Schema Structure Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-xs">
        <div className="p-4 border-b border-border flex items-center gap-2">
          <Table className="h-4 w-4 text-primary" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
            Schema Columns & Constraints
          </h4>
        </div>
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/50 border-b border-border text-muted-foreground">
            <tr>
              <th className="p-3">Column Name</th>
              <th className="p-3">Data Type</th>
              <th className="p-3">Nullable</th>
              <th className="p-3">Key Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60 font-mono">
            {sampleDataset.schema.map((col) => (
              <tr key={col.name} className="hover:bg-muted/30">
                <td className="p-3 font-semibold text-foreground">{col.name}</td>
                <td className="p-3 text-primary">{col.type}</td>
                <td className="p-3">{col.nullable ? "YES" : "NO"}</td>
                <td className="p-3">{col.pk ? "PRIMARY KEY" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
