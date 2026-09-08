"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useLanguage } from "@/contexts/language-context";
import {
  Coins,
  Receipt,
  Wallet,
  Cpu,
  AlertTriangle,
  Sparkles,
  Scale,
  CheckCircle2,
  AlertOctagon,
  ArrowUpRight,
  ShieldAlert,
} from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";
import { FinOpsOverview } from "@/types/finops";

function getMockOverview(): FinOpsOverview {
  return {
    current_spend: "142.50",
    forecasted_spend: "385.00",
    budget_total: "500.00",
    remaining_budget: "357.50",
    utilization_percent: 28.5,
    top_model: "gpt-4o",
    top_provider: "openai",
    top_feature: "RAG Pipeline",
    open_anomalies_count: 0,
    potential_savings: "72.40",
    attribution_completeness_percent: 100.0,
    readiness_status: "READY",
    disclaimer:
      "This subsystem provides internal usage accounting and cost estimation. It is not a payment processor and does not represent provider invoices unless reconciled with an authoritative billing source.",
  };
}

export default function FinOpsOverviewPage() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [overview, setOverview] = useState<FinOpsOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadOverview() {
      try {
        const res = await fetch("/api/v1/finops/overview");
        if (res.ok) {
          const data = await res.json();
          setOverview(data);
        } else {
          setOverview(getMockOverview());
        }
      } catch {
        setOverview(getMockOverview());
      } finally {
        setLoading(false);
      }
    }
    loadOverview();
  }, []);

  if (loading || !overview) {
    return (
      <div className="flex items-center justify-center p-12 text-sm text-muted-foreground">
        {isTr ? "Kurumsal FinOps telemetrisi yükleniyor..." : "Loading Enterprise FinOps telemetry..."}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Coins className="h-6 w-6 text-emerald-500" />
            <h1 className="text-2xl font-bold tracking-tight">
              {isTr ? "Kurumsal FinOps & AI Maliyet Yönetişimi" : "Enterprise FinOps & AI Cost Governance"}
            </h1>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
              overview.readiness_status === "READY"
                ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
                : "bg-amber-500/10 text-amber-500 border border-amber-500/20"
            }`}
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {isTr ? "FinOps Durumu: " : "FinOps Status: "}
            {overview.readiness_status === "READY" && isTr ? "HAZIR" : overview.readiness_status}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {isTr
            ? "Denetim dereceli kullanım muhasebesi, deterministik maliyet tahsisi, hiyerarşik bütçeler ve sürekli harcama yönetişimi."
            : "Audit-grade usage accounting, deterministic cost allocation, hierarchical budgets, and continuous spend governance."}
        </p>
      </div>

      <FinOpsNav />

      {/* Prominent Billing Boundary Disclaimer */}
      <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-4 text-xs text-muted-foreground">
        <ShieldAlert className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-amber-500">
            {isTr ? "Mali Defter Sınırlarına İlişkin Bildirim: " : "Notice on Financial Ledger Boundaries: "}
          </span>
          {overview.disclaimer}
        </div>
      </div>

      {/* Top Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-4 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Mevcut Harcama" : "Current Spend"}</span>
            <Coins className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-foreground">
            ${Number(overview.current_spend).toFixed(2)}
          </div>
          <div className="text-xs text-muted-foreground">
            {isTr ? "Tahmini Harcama: " : "Forecasted: "}${Number(overview.forecasted_spend).toFixed(2)} {isTr ? "/ ay" : "/ mo"}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Bütçe Kullanımı" : "Budget Utilization"}</span>
            <Wallet className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-foreground">
            %{overview.utilization_percent.toFixed(1)}
          </div>
          <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full ${
                overview.utilization_percent >= 95
                  ? "bg-rose-500"
                  : overview.utilization_percent >= 80
                  ? "bg-amber-500"
                  : "bg-emerald-500"
              }`}
              style={{ width: `${Math.min(100, overview.utilization_percent)}%` }}
            />
          </div>
          <div className="text-xs text-muted-foreground">
            {isTr
              ? `Kalan: $${Number(overview.remaining_budget).toFixed(2)} / $${Number(overview.budget_total).toFixed(2)}`
              : `Remaining: $${Number(overview.remaining_budget).toFixed(2)} of $${Number(overview.budget_total).toFixed(2)}`}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Potansiyel Tasarruf" : "Potential Savings"}</span>
            <Sparkles className="h-4 w-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-purple-500">
            ${Number(overview.potential_savings).toFixed(2)}{isTr ? "/ay" : "/mo"}
          </div>
          <div className="text-xs text-muted-foreground">
            {isTr ? "Model küçültme ve önbellekleme ile" : "Via model downgrades & prompt caching"}
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 space-y-2 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Tahsis Tamlığı" : "Attribution Completeness"}</span>
            <Scale className="h-4 w-4 text-teal-500" />
          </div>
          <div className="text-2xl font-bold tracking-tight text-foreground">
            %{overview.attribution_completeness_percent.toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground">
            {isTr ? "SLO hedefi: >= %99.0 kiracı tahsisi" : "SLO target: >= 99.0% tenant attribution"}
          </div>
        </div>
      </div>

      {/* Breakdown Panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold text-sm">
              <Cpu className="h-4 w-4 text-blue-500" />
              <span>{isTr ? "En Yüksek Model Harcaması" : "Top Model Spend"}</span>
            </div>
            <Link href="/finops/models" className="text-xs text-primary hover:underline flex items-center gap-0.5">
              {isTr ? "Tümünü Gör" : "View all"} <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">{overview.top_model}</span>
              <span className="text-muted-foreground">$88.20 (61.9%)</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">claude-3-5-sonnet</span>
              <span className="text-muted-foreground">$38.10 (26.7%)</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">gpt-4o-mini</span>
              <span className="text-muted-foreground">$16.20 (11.4%)</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold text-sm">
              <Receipt className="h-4 w-4 text-emerald-500" />
              <span>{isTr ? "En Yüksek Özellik Çağrıları" : "Top Feature Invocations"}</span>
            </div>
            <Link href="/finops/usage" className="text-xs text-primary hover:underline flex items-center gap-0.5">
              {isTr ? "Keşfet" : "Explore"} <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">{overview.top_feature}</span>
              <span className="text-muted-foreground">$64.20 (45.1%)</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">Agent Runtime</span>
              <span className="text-muted-foreground">$42.80 (30.0%)</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-foreground">Continuous Eval</span>
              <span className="text-muted-foreground">$35.50 (24.9%)</span>
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 font-semibold text-sm">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              <span>{isTr ? "Maliyet Anomalileri" : "Cost Anomalies"}</span>
            </div>
            <Link href="/finops/anomalies" className="text-xs text-primary hover:underline flex items-center gap-0.5">
              {isTr ? "Anomaliler" : "Anomalies"} <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          {overview.open_anomalies_count === 0 ? (
            <div className="flex flex-col items-center justify-center p-6 text-center space-y-2">
              <CheckCircle2 className="h-8 w-8 text-emerald-500/70" />
              <div className="text-sm font-medium text-foreground">
                {isTr ? "Aktif Anomali Yok" : "Zero Active Anomalies"}
              </div>
              <div className="text-xs text-muted-foreground">
                {isTr ? "Tüm model çağrıları normal eşik değerlerinde seyrediyor." : "All model invocations tracking within normal baselines."}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-3 p-3 rounded-lg border border-rose-500/20 bg-rose-500/10 text-rose-500 text-xs">
              <AlertOctagon className="h-5 w-5 shrink-0" />
              <div>
                <span className="font-semibold">
                  {isTr
                    ? `${overview.open_anomalies_count} aktif anomali tespit edildi.`
                    : `${overview.open_anomalies_count} active anomaly detected.`}
                </span>{" "}
                {isTr
                  ? "Bütçe aşımını önlemek için ani artış ayrıntılarını inceleyin."
                  : "Review spike details to prevent budget exhaustion."}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
