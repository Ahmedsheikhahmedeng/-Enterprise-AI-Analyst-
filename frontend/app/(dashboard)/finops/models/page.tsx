"use client";

import React, { useState, useEffect } from "react";
import { Cpu } from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";

interface ModelCostSummary {
  model: string;
  provider: string;
  total_tokens: number;
  total_cost: number;
  request_count: number;
  avg_cost_per_request: number;
  quality_score: number | string;
}

function getMockModels(): ModelCostSummary[] {
  return [
    {
      model: "gpt-4o",
      provider: "openai",
      total_tokens: 12500000,
      total_cost: 88.20,
      request_count: 4200,
      avg_cost_per_request: 0.0210,
      quality_score: 0.94,
    },
    {
      model: "claude-3-5-sonnet",
      provider: "anthropic",
      total_tokens: 5800000,
      total_cost: 38.10,
      request_count: 1850,
      avg_cost_per_request: 0.0206,
      quality_score: 0.93,
    },
    {
      model: "gpt-4o-mini",
      provider: "openai",
      total_tokens: 28400000,
      total_cost: 16.20,
      request_count: 8900,
      avg_cost_per_request: 0.0018,
      quality_score: 0.86,
    },
    {
      model: "text-embedding-3-small",
      provider: "openai",
      total_tokens: 15000000,
      total_cost: 0.30,
      request_count: 6200,
      avg_cost_per_request: 0.000048,
      quality_score: "N/A",
    },
  ];
}

export default function FinOpsModelsPage() {
  const [models, setModels] = useState<ModelCostSummary[]>([]);

  useEffect(() => {
    async function loadModels() {
      try {
        const res = await fetch("/api/v1/finops/costs/by-model");
        if (res.ok) {
          const data = await res.json();
          setModels(data.items || getMockModels());
        } else {
          setModels(getMockModels());
        }
      } catch {
        setModels(getMockModels());
      }
    }
    loadModels();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Cpu className="h-6 w-6 text-purple-500" />
          <h1 className="text-2xl font-bold tracking-tight">AI Model Cost & Efficiency Breakdown</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Analyze token expenditure, average cost per request, and quality correlation across registered models.
        </p>
      </div>

      <FinOpsNav />

      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <table className="w-full text-xs text-left">
          <thead className="bg-muted/50 text-muted-foreground uppercase border-b border-border text-[10px]">
            <tr>
              <th className="px-4 py-3">Model</th>
              <th className="px-4 py-3">Provider</th>
              <th className="px-4 py-3 text-right">Total Tokens</th>
              <th className="px-4 py-3 text-right">Invocations</th>
              <th className="px-4 py-3 text-right">Avg Cost / Req</th>
              <th className="px-4 py-3 text-right">Quality Score</th>
              <th className="px-4 py-3 text-right">Total Spend (USD)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {models.map((m) => (
              <tr key={m.model} className="hover:bg-accent/40 transition-colors">
                <td className="px-4 py-3 font-semibold text-foreground font-mono">{m.model}</td>
                <td className="px-4 py-3 text-muted-foreground capitalize">{m.provider}</td>
                <td className="px-4 py-3 text-right font-mono">{m.total_tokens.toLocaleString()}</td>
                <td className="px-4 py-3 text-right font-mono">{m.request_count.toLocaleString()}</td>
                <td className="px-4 py-3 text-right font-mono">${m.avg_cost_per_request.toFixed(5)}</td>
                <td className="px-4 py-3 text-right">
                  {typeof m.quality_score === "number" ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-500">
                      {(m.quality_score * 100).toFixed(0)}%
                    </span>
                  ) : (
                    <span className="text-muted-foreground text-[10px]">N/A</span>
                  )}
                </td>
                <td className="px-4 py-3 text-right font-mono font-bold text-foreground">
                  ${m.total_cost.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
