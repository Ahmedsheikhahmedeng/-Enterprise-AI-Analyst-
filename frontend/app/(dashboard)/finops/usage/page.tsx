"use client";

import React, { useState, useEffect } from "react";
import { Receipt, Filter } from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";
import { CostEvent } from "@/types/finops";

function getMockUsage(): CostEvent[] {
  return [
    {
      id: "evt-01",
      provider: "openai",
      model: "gpt-4o",
      operation: "CHAT",
      input_tokens: 1250,
      output_tokens: 420,
      cached_tokens: 250,
      total_tokens: 1670,
      estimated_cost: "0.01255000",
      currency: "USD",
      pricing_version: 1,
      timestamp: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
      is_retry: false,
      is_failed: false,
    },
    {
      id: "evt-02",
      provider: "anthropic",
      model: "claude-3-5-sonnet",
      operation: "RAG",
      input_tokens: 3400,
      output_tokens: 850,
      cached_tokens: 1200,
      total_tokens: 4250,
      estimated_cost: "0.02331000",
      currency: "USD",
      pricing_version: 1,
      timestamp: new Date(Date.now() - 1000 * 60 * 35).toISOString(),
      is_retry: false,
      is_failed: false,
    },
    {
      id: "evt-03",
      provider: "openai",
      model: "gpt-4o-mini",
      operation: "SQL",
      input_tokens: 820,
      output_tokens: 180,
      cached_tokens: 0,
      total_tokens: 1000,
      estimated_cost: "0.00023100",
      currency: "USD",
      pricing_version: 1,
      timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
      is_retry: false,
      is_failed: false,
    },
    {
      id: "evt-04",
      provider: "openai",
      model: "gpt-4o",
      operation: "AGENT",
      input_tokens: 4500,
      output_tokens: 1100,
      cached_tokens: 800,
      total_tokens: 5600,
      estimated_cost: "0.04100000",
      currency: "USD",
      pricing_version: 1,
      timestamp: new Date(Date.now() - 1000 * 60 * 95).toISOString(),
      is_retry: false,
      is_failed: false,
    },
    {
      id: "evt-05",
      provider: "anthropic",
      model: "claude-3-5-sonnet",
      operation: "EVALUATION",
      input_tokens: 2800,
      output_tokens: 600,
      cached_tokens: 400,
      total_tokens: 3400,
      estimated_cost: "0.01752000",
      currency: "USD",
      pricing_version: 1,
      timestamp: new Date(Date.now() - 1000 * 60 * 150).toISOString(),
      is_retry: false,
      is_failed: false,
    },
  ];
}

export default function FinOpsUsagePage() {
  const [events, setEvents] = useState<CostEvent[]>([]);
  const [operationFilter, setOperationFilter] = useState<string>("ALL");

  useEffect(() => {
    async function loadEvents() {
      try {
        const res = await fetch("/api/v1/finops/usage");
        if (res.ok) {
          const data = await res.json();
          setEvents(data.items || getMockUsage());
        } else {
          setEvents(getMockUsage());
        }
      } catch {
        setEvents(getMockUsage());
      }
    }
    loadEvents();
  }, []);

  const filteredEvents = events.filter((e) => {
    if (operationFilter === "ALL") return true;
    return e.operation === operationFilter;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Receipt className="h-6 w-6 text-emerald-500" />
          <h1 className="text-2xl font-bold tracking-tight">Usage Explorer & Cost Ledger</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Immutable, append-only usage telemetry events recording deterministic token pricing and tenant attribution.
        </p>
      </div>

      <FinOpsNav />

      {/* Filter Bar */}
      <div className="flex items-center justify-between gap-4 border border-border bg-card p-3 rounded-lg">
        <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Filter className="h-4 w-4" />
          <span>Filter Operation:</span>
          {["ALL", "CHAT", "RAG", "SQL", "AGENT", "EVALUATION"].map((op) => (
            <button
              key={op}
              onClick={() => setOperationFilter(op)}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                operationFilter === op
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-accent"
              }`}
            >
              {op}
            </button>
          ))}
        </div>
        <div className="text-xs text-muted-foreground">
          Showing {filteredEvents.length} recorded cost events
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-muted/50 text-muted-foreground uppercase border-b border-border text-[10px]">
              <tr>
                <th className="px-4 py-3">Event ID & Timestamp</th>
                <th className="px-4 py-3">Provider & Model</th>
                <th className="px-4 py-3">Operation</th>
                <th className="px-4 py-3 text-right">Input Tokens</th>
                <th className="px-4 py-3 text-right">Output Tokens</th>
                <th className="px-4 py-3 text-right">Cached Tokens</th>
                <th className="px-4 py-3 text-right">Estimated Cost (USD)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredEvents.map((evt) => (
                <tr key={evt.id} className="hover:bg-accent/40 transition-colors">
                  <td className="px-4 py-3 font-mono">
                    <div className="font-semibold text-foreground">{evt.id}</div>
                    <div className="text-[10px] text-muted-foreground">
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="capitalize font-medium text-foreground">{evt.provider}</span>
                    <span className="text-muted-foreground text-[10px] block font-mono">{evt.model}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-muted text-foreground border border-border">
                      {evt.operation}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono">{evt.input_tokens.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right font-mono">{evt.output_tokens.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right font-mono text-emerald-500">
                    {evt.cached_tokens > 0 ? evt.cached_tokens.toLocaleString() : "-"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-bold text-foreground">
                    ${Number(evt.estimated_cost).toFixed(6)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
