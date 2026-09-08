"use client";

import React from "react";
import { EvaluationDashboard } from "@/features/evaluation/evaluation-dashboard";
import { useEvaluationScorecards } from "@/hooks/use-platform";
import { useLanguage } from "@/contexts/language-context";
import { Award } from "lucide-react";

const SAMPLE_SCORECARDS = [
  {
    suite_id: "eval-001",
    name: "Financial RAG Grounding & Retrieval Benchmark v2",
    overall_quality: 0.965,
    grounding_score: 0.982,
    citation_precision: 0.964,
    retrieval_ndcg: 0.931,
    sql_accuracy: 0.99,
    decision: "PASS" as const,
    delta_from_baseline: 0.014,
    timestamp: "2026-09-07T18:00:00.000Z",
  },
  {
    suite_id: "eval-002",
    name: "Complex SQL Multi-Table Aggregation Benchmark",
    overall_quality: 0.942,
    grounding_score: 0.975,
    citation_precision: 0.938,
    retrieval_ndcg: 0.912,
    sql_accuracy: 0.985,
    decision: "PASS" as const,
    delta_from_baseline: 0.008,
    timestamp: "2026-09-06T18:00:00.000Z",
  },
  {
    suite_id: "eval-003",
    name: "Adversarial Prompt & Hallucination Resistance",
    overall_quality: 0.988,
    grounding_score: 0.995,
    citation_precision: 0.982,
    retrieval_ndcg: 0.954,
    sql_accuracy: 0.998,
    decision: "PASS" as const,
    delta_from_baseline: 0.021,
    timestamp: "2026-09-05T18:00:00.000Z",
  },
];

export default function EvaluationPage() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const { data } = useEvaluationScorecards();
  const sampleScorecards = data && data.length > 0 ? data : SAMPLE_SCORECARDS;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600">
          <Award className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            {isTr ? "Sürekli AI Kalitesi & Kıyaslama Takibi" : "Continuous AI Quality & Benchmark Monitoring"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "Gerçek zamanlı kalite kapıları, istatistiksel regresyon takibi ve kalibrasyon metrikleri."
              : "Real-time quality gates, statistical regression tracking, and calibration metrics."}
          </p>
        </div>
      </div>

      <EvaluationDashboard scorecards={sampleScorecards} />
    </div>
  );
}
