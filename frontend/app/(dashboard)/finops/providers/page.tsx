"use client";

import React, { useState, useEffect } from "react";
import { Cloud } from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";

interface ProviderCostSummary {
  provider: string;
  total_tokens: number;
  total_cost: number;
  request_count: number;
  market_share_percent: number;
}

function getMockProviders(): ProviderCostSummary[] {
  return [
    {
      provider: "openai",
      total_tokens: 55900000,
      total_cost: 104.70,
      request_count: 19300,
      market_share_percent: 73.5,
    },
    {
      provider: "anthropic",
      total_tokens: 5800000,
      total_cost: 38.10,
      request_count: 1850,
      market_share_percent: 26.7,
    },
    {
      provider: "ollama (local)",
      total_tokens: 8200000,
      total_cost: 0.00,
      request_count: 4500,
      market_share_percent: 0.0,
    },
  ];
}

export default function FinOpsProvidersPage() {
  const [providers, setProviders] = useState<ProviderCostSummary[]>([]);

  useEffect(() => {
    async function loadProviders() {
      try {
        const res = await fetch("/api/v1/finops/costs/by-provider");
        if (res.ok) {
          const data = await res.json();
          setProviders(data.items || getMockProviders());
        } else {
          setProviders(getMockProviders());
        }
      } catch {
        setProviders(getMockProviders());
      }
    }
    loadProviders();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Cloud className="h-6 w-6 text-blue-500" />
          <h1 className="text-2xl font-bold tracking-tight">AI Provider Cost & Consumption</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Vendor concentration, total compute spend, and token volume distribution across integrated LLM providers.
        </p>
      </div>

      <FinOpsNav />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {providers.map((p) => (
          <div key={p.provider} className="rounded-xl border border-border bg-card p-5 space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-base capitalize text-foreground flex items-center gap-1.5">
                <Cloud className="h-4 w-4 text-primary" /> {p.provider}
              </span>
              <span className="text-[10px] font-semibold text-muted-foreground">
                {p.market_share_percent.toFixed(1)}% spend
              </span>
            </div>

            <div className="space-y-1">
              <div className="text-2xl font-bold text-foreground">${p.total_cost.toFixed(2)}</div>
              <div className="text-xs text-muted-foreground">
                {p.request_count.toLocaleString()} calls | {p.total_tokens.toLocaleString()} tokens
              </div>
            </div>

            <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-primary h-full"
                style={{ width: `${Math.min(100, p.market_share_percent)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
