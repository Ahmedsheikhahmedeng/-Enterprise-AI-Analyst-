"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Calculator, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function MetricsPage() {
  const sampleMetrics = [
    {
      id: "met-001",
      name: "Gross Operating Margin",
      formula: "((total_revenue - cost_of_goods_sold) / total_revenue) * 100",
      status: "PUBLISHED",
      unit: "PERCENTAGE",
    },
    {
      id: "met-002",
      name: "Customer Acquisition Cost (CAC)",
      formula: "total_sales_and_marketing_expenses / total_new_customers_acquired",
      status: "PUBLISHED",
      unit: "USD",
    },
    {
      id: "met-003",
      name: "Quick Ratio",
      formula: "(cash_and_equivalents + marketable_securities + accounts_receivable) / current_liabilities",
      status: "APPROVED",
      unit: "RATIO",
    },
  ];

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
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-500">
          <Calculator className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            Verified Calculated Metrics
          </h1>
          <p className="text-xs text-muted-foreground">
            Deterministic formula registry consumed by SQL synthesis agent.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {sampleMetrics.map((met) => (
          <div
            key={met.id}
            className="rounded-xl border border-border bg-card p-4 space-y-2 shadow-xs"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-foreground">{met.name}</span>
                <span className="rounded bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-primary">
                  {met.unit}
                </span>
              </div>
              <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                <ShieldCheck className="h-3 w-3" />
                {met.status}
              </span>
            </div>

            <div className="rounded-lg bg-muted/40 p-2.5 font-mono text-[11px] text-foreground/90 border border-border/40 overflow-x-auto">
              {met.formula}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
