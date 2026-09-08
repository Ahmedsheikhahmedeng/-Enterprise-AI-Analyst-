"use client";

import React from "react";
import { EvaluationScorecard } from "@/types/platform";
import { useLanguage } from "@/contexts/language-context";
import { formatPercent } from "@/lib/utils";
import { CheckCircle2, AlertTriangle, XCircle, TrendingUp, ShieldAlert } from "lucide-react";

interface EvaluationDashboardProps {
  scorecards: EvaluationScorecard[];
}

export function EvaluationDashboard({ scorecards }: EvaluationDashboardProps) {
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case "PASS":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 px-2.5 py-0.5 text-xs font-bold border border-emerald-500/30">
            <CheckCircle2 className="h-3.5 w-3.5" />
            {isTr ? "GEÇTİ" : "PASS"}
          </span>
        );
      case "WARN":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400 px-2.5 py-0.5 text-xs font-bold border border-amber-500/30">
            <AlertTriangle className="h-3.5 w-3.5" />
            {isTr ? "UYARI" : "WARN"}
          </span>
        );
      case "BLOCK_RELEASE":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 px-2.5 py-0.5 text-xs font-bold border border-rose-500/30">
            <ShieldAlert className="h-3.5 w-3.5" />
            {isTr ? "YAYINI ENGELLE" : "BLOCK RELEASE"}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-destructive/15 text-destructive px-2.5 py-0.5 text-xs font-bold border border-destructive/30">
            <XCircle className="h-3.5 w-3.5" />
            {isTr ? "BAŞARISIZ" : "FAIL"}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-4 space-y-1 shadow-xs">
          <span className="text-xs text-muted-foreground font-medium">
            {isTr ? "Genel AI Kalitesi" : "Overall AI Quality"}
          </span>
          <div className="text-2xl font-bold font-mono text-foreground">96.4%</div>
          <div className="flex items-center gap-1 text-[11px] text-emerald-600 font-semibold">
            <TrendingUp className="h-3 w-3" />
            <span>{isTr ? "+1.2% temel çizgiden" : "+1.2% from baseline"}</span>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 space-y-1 shadow-xs">
          <span className="text-xs text-muted-foreground font-medium">
            {isTr ? "Dayanak Hassasiyeti" : "Grounding Precision"}
          </span>
          <div className="text-2xl font-bold font-mono text-foreground">98.1%</div>
          <span className="text-[11px] text-muted-foreground">
            {isTr ? "Sıfır halüsinasyon eşiği" : "Zero hallucination threshold"}
          </span>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 space-y-1 shadow-xs">
          <span className="text-xs text-muted-foreground font-medium">
            {isTr ? "Alıntı Doğruluğu" : "Citation Accuracy"}
          </span>
          <div className="text-2xl font-bold font-mono text-foreground">95.8%</div>
          <span className="text-[11px] text-muted-foreground">
            {isTr ? "Doğrudan temel gerçeklik eşlemesi" : "Direct ground-truth mapping"}
          </span>
        </div>

        <div className="rounded-xl border border-border bg-card p-4 space-y-1 shadow-xs">
          <span className="text-xs text-muted-foreground font-medium">
            {isTr ? "SQL Kesin Çalıştırma" : "SQL Exact Execution"}
          </span>
          <div className="text-2xl font-bold font-mono text-foreground">99.2%</div>
          <div className="flex items-center gap-1 text-[11px] text-emerald-600 font-semibold">
            <CheckCircle2 className="h-3 w-3" />
            <span>{isTr ? "Kalite kapısını geçti" : "Passes quality gate"}</span>
          </div>
        </div>
      </div>

      {/* Scorecards Table */}
      <div className="rounded-xl border border-border bg-card shadow-xs overflow-hidden">
        <div className="p-4 border-b border-border">
          <h4 className="text-xs font-bold uppercase tracking-wider text-foreground">
            {isTr ? "Sürekli Değerlendirme Kıyaslamaları & Kalite Kapıları" : "Continuous Evaluation Benchmarks & Quality Gates"}
          </h4>
        </div>

        <table className="w-full text-left text-xs">
          <thead className="bg-muted/50 border-b border-border text-muted-foreground">
            <tr>
              <th className="p-3.5">{isTr ? "Paket Adı" : "Suite Name"}</th>
              <th className="p-3.5">{isTr ? "Genel Kalite" : "Overall Quality"}</th>
              <th className="p-3.5">{isTr ? "Dayanak" : "Grounding"}</th>
              <th className="p-3.5">{isTr ? "Alıntı" : "Citation"}</th>
              <th className="p-3.5">{isTr ? "Geri Getirme" : "Retrieval"}</th>
              <th className="p-3.5">{isTr ? "SQL Doğruluğu" : "SQL Accuracy"}</th>
              <th className="p-3.5">{isTr ? "Fark" : "Delta"}</th>
              <th className="p-3.5 text-right">{isTr ? "Kapı Kararı" : "Gate Decision"}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {scorecards.map((s) => (
              <tr key={s.suite_id} className="hover:bg-muted/30 transition-colors">
                <td className="p-3.5 font-semibold text-foreground">{s.name}</td>
                <td className="p-3.5 font-mono font-bold">{formatPercent(s.overall_quality)}</td>
                <td className="p-3.5 font-mono">{formatPercent(s.grounding_score)}</td>
                <td className="p-3.5 font-mono">{formatPercent(s.citation_precision)}</td>
                <td className="p-3.5 font-mono">{formatPercent(s.retrieval_ndcg)}</td>
                <td className="p-3.5 font-mono">{formatPercent(s.sql_accuracy)}</td>
                <td className="p-3.5 font-mono text-emerald-600 font-semibold">
                  {s.delta_from_baseline != null ? `+${(s.delta_from_baseline * 100).toFixed(1)}%` : "—"}
                </td>
                <td className="p-3.5 text-right">{getDecisionBadge(s.decision)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
