"use client";

import React, { useState, useEffect } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";
import { CostAnomaly } from "@/types/finops";

function getMockAnomalies(): CostAnomaly[] {
  return [
    {
      id: "ano-01",
      organization_id: "org-primary",
      anomaly_type: "SUDDEN_SPIKE",
      severity: "WARNING",
      status: "OPEN",
      baseline_amount: "12.50",
      actual_amount: "28.40",
      deviation_percent: 127.2,
      estimated_impact: "15.90",
      description: "Hourly spend spike detected on 'financial-analyst-v1': Actual spend ($28.40) deviated by +127.2% from rolling baseline ($12.50).",
      affected_entity: "financial-analyst-v1",
      detected_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    },
  ];
}

export default function FinOpsAnomaliesPage() {
  const [anomalies, setAnomalies] = useState<CostAnomaly[]>([]);

  useEffect(() => {
    async function loadAnomalies() {
      try {
        const res = await fetch("/api/v1/finops/anomalies");
        if (res.ok) {
          const data = await res.json();
          setAnomalies(data.items || getMockAnomalies());
        } else {
          setAnomalies(getMockAnomalies());
        }
      } catch {
        setAnomalies(getMockAnomalies());
      }
    }
    loadAnomalies();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-6 w-6 text-amber-500" />
          <h1 className="text-2xl font-bold tracking-tight">Deterministic Cost & Token Anomaly Detection</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Continuous moving-average deviation tracking to flag runaway agent loops, token surges, and unexpected spikes.
        </p>
      </div>

      <FinOpsNav />

      {anomalies.length === 0 ? (
        <div className="rounded-xl border border-border bg-card p-12 text-center space-y-3 shadow-sm">
          <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
          <div className="text-base font-semibold text-foreground">Zero Active Cost Anomalies</div>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            All workload invocations and token consumption patterns are operating strictly within baseline confidence bounds.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {anomalies.map((ano) => (
            <div
              key={ano.id}
              className="rounded-xl border border-amber-500/30 bg-card p-5 space-y-3 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-bold ${
                      ano.severity === "CRITICAL"
                        ? "bg-rose-500/10 text-rose-500 border border-rose-500/20"
                        : "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                    }`}
                  >
                    {ano.severity}
                  </span>
                  <span className="font-semibold text-sm text-foreground">{ano.anomaly_type}</span>
                </div>
                <span className="text-[10px] font-mono text-muted-foreground">
                  Detected: {new Date(ano.detected_at).toLocaleTimeString()}
                </span>
              </div>

              <p className="text-xs text-foreground/90">{ano.description}</p>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 text-xs border-t border-border">
                <div>
                  <span className="text-muted-foreground block text-[10px]">Baseline Amount</span>
                  <span className="font-mono font-medium text-foreground">${Number(ano.baseline_amount).toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px]">Actual Spiked Spend</span>
                  <span className="font-mono font-bold text-foreground">${Number(ano.actual_amount).toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px]">Deviation</span>
                  <span className="font-mono font-semibold text-rose-500">+{ano.deviation_percent.toFixed(1)}%</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px]">Estimated Financial Impact</span>
                  <span className="font-mono font-bold text-amber-500">${Number(ano.estimated_impact).toFixed(2)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
