"use client";

import React, { useState, useEffect } from "react";
import { Wallet, ShieldCheck, CheckCircle2, Clock } from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";
import { Budget, Quota } from "@/types/finops";

function getMockBudgets(): Budget[] {
  return [
    {
      id: "bg-01",
      organization_id: "org-primary",
      scope: "ORGANIZATION",
      period: "MONTHLY",
      limit_amount: "500.00",
      currency: "USD",
      warning_percent: 80,
      critical_percent: 95,
      enabled: true,
      starts_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 10).toISOString(),
    },
    {
      id: "bg-02",
      organization_id: "org-primary",
      scope: "AGENT",
      scope_id: "financial-analyst-v1",
      period: "MONTHLY",
      limit_amount: "150.00",
      currency: "USD",
      warning_percent: 80,
      critical_percent: 95,
      enabled: true,
      starts_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 10).toISOString(),
    },
    {
      id: "bg-03",
      organization_id: "org-primary",
      scope: "FEATURE",
      scope_id: "evaluations",
      period: "MONTHLY",
      limit_amount: "100.00",
      currency: "USD",
      warning_percent: 80,
      critical_percent: 95,
      enabled: true,
      starts_at: new Date(Date.now() - 1000 * 60 * 60 * 24 * 10).toISOString(),
    },
  ];
}

function getMockQuotas(): Quota[] {
  return [
    {
      id: "q-01",
      organization_id: "org-primary",
      quota_type: "TOKENS",
      scope: "ORGANIZATION",
      limit_value: "5000000",
      period_seconds: 86400,
      enforcement_mode: "BLOCK",
      enabled: true,
    },
    {
      id: "q-02",
      organization_id: "org-primary",
      quota_type: "REQUESTS",
      scope: "ORGANIZATION",
      limit_value: "1000",
      period_seconds: 3600,
      enforcement_mode: "THROTTLE",
      enabled: true,
    },
    {
      id: "q-03",
      organization_id: "org-primary",
      quota_type: "COST",
      scope: "USER",
      limit_value: "50.00",
      period_seconds: 86400 * 30,
      enforcement_mode: "WARN",
      enabled: true,
    },
  ];
}

export default function FinOpsBudgetsPage() {
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [quotas, setQuotas] = useState<Quota[]>([]);

  useEffect(() => {
    async function loadData() {
      try {
        const [resB, resQ] = await Promise.all([
          fetch("/api/v1/finops/budgets"),
          fetch("/api/v1/finops/quotas"),
        ]);
        if (resB.ok) {
          const bData = await resB.json();
          setBudgets(bData.items || getMockBudgets());
        } else {
          setBudgets(getMockBudgets());
        }
        if (resQ.ok) {
          const qData = await resQ.json();
          setQuotas(qData.items || getMockQuotas());
        } else {
          setQuotas(getMockQuotas());
        }
      } catch {
        setBudgets(getMockBudgets());
        setQuotas(getMockQuotas());
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Wallet className="h-6 w-6 text-blue-500" />
          <h1 className="text-2xl font-bold tracking-tight">Hierarchical Budgets & Rate Quotas</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Enforce spending ceilings across organizations, agents, and features with deterministic preflight blocking.
        </p>
      </div>

      <FinOpsNav />

      {/* Budgets Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <Wallet className="h-4 w-4 text-blue-500" /> Active Spending Budgets
          </h2>
          <span className="text-xs text-muted-foreground">{budgets.length} configured budgets</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {budgets.map((b) => (
            <div key={b.id} className="rounded-xl border border-border bg-card p-5 space-y-3 shadow-sm">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-muted text-foreground border border-border">
                  {b.scope} {b.scope_id ? `(${b.scope_id})` : ""}
                </span>
                <span className="text-[10px] font-semibold text-emerald-500 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" /> SPENDING
                </span>
              </div>

              <div className="space-y-1">
                <div className="text-xs text-muted-foreground">Allocated {b.period.toLowerCase()} ceiling</div>
                <div className="text-xl font-bold text-foreground">${Number(b.limit_amount).toFixed(2)} USD</div>
              </div>

              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>Thresholds</span>
                  <span>Warn: {b.warning_percent}% | Crit: {b.critical_percent}%</span>
                </div>
                <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                  <div className="bg-emerald-500 h-full w-[28%]" />
                </div>
              </div>

              <div className="pt-2 border-t border-border flex items-center justify-between text-[10px] text-muted-foreground">
                <span className="font-mono">{b.id}</span>
                <span>Active since {new Date(b.starts_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quotas Section */}
      <div className="space-y-3 pt-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-500" /> Multi-Dimensional Resource Quotas
          </h2>
          <span className="text-xs text-muted-foreground">{quotas.length} rate quotas</span>
        </div>

        <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
          <table className="w-full text-xs text-left">
            <thead className="bg-muted/50 text-muted-foreground uppercase border-b border-border text-[10px]">
              <tr>
                <th className="px-4 py-3">Quota ID</th>
                <th className="px-4 py-3">Dimension</th>
                <th className="px-4 py-3">Scope</th>
                <th className="px-4 py-3">Limit Value</th>
                <th className="px-4 py-3">Rolling Window</th>
                <th className="px-4 py-3">Mode</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {quotas.map((q) => (
                <tr key={q.id} className="hover:bg-accent/40 transition-colors">
                  <td className="px-4 py-3 font-mono font-medium text-foreground">{q.id}</td>
                  <td className="px-4 py-3 font-semibold text-foreground">{q.quota_type}</td>
                  <td className="px-4 py-3 text-muted-foreground">{q.scope}</td>
                  <td className="px-4 py-3 font-mono font-bold text-foreground">
                    {q.quota_type === "COST" ? `$${Number(q.limit_value).toFixed(2)}` : Number(q.limit_value).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3 text-muted-foreground" />
                    {q.period_seconds >= 86400
                      ? `${Math.round(q.period_seconds / 86400)} day(s)`
                      : `${Math.round(q.period_seconds / 3600)} hour(s)`}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold ${
                        q.enforcement_mode === "BLOCK"
                          ? "bg-rose-500/10 text-rose-500 border border-rose-500/20"
                          : q.enforcement_mode === "THROTTLE"
                          ? "bg-amber-500/10 text-amber-500 border border-amber-500/20"
                          : "bg-blue-500/10 text-blue-500 border border-blue-500/20"
                      }`}
                    >
                      {q.enforcement_mode}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-[10px] font-medium text-emerald-500 flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3" /> Enabled
                    </span>
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
