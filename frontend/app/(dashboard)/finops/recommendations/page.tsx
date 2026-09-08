"use client";

import React, { useState, useEffect } from "react";
import { Sparkles } from "lucide-react";
import { FinOpsNav } from "@/components/finops/finops-nav";
import { OptimizationRecommendation } from "@/types/finops";

function getMockRecommendations(): OptimizationRecommendation[] {
  return [
    {
      id: "rec-01",
      organization_id: "org-primary",
      recommendation_type: "SWITCH_TO_LOWER_COST_MODEL",
      status: "OPEN",
      title: "Migrate routine classification from 'gpt-4o' to 'gpt-4o-mini'",
      description: "Detected 4,200 invocations on 'gpt-4o' executing standard classification and tagging. Switching eligible standard queries to 'gpt-4o-mini' can save up to $48.20/month with zero quality degradation.",
      current_cost: "62.50",
      expected_saving: "48.20",
      quality_impact: "NEGLIGIBLE",
      latency_impact: "FASTER",
      confidence: 0.88,
      evidence: { target_model: "gpt-4o-mini", estimated_discount: "77%" },
    },
    {
      id: "rec-02",
      organization_id: "org-primary",
      recommendation_type: "ENABLE_CACHING",
      status: "OPEN",
      title: "Enable Prompt Caching on Repeated System Instructions",
      description: "Over 1.8M input tokens per week represent static system prompt definitions in RAG queries. Enabling Anthropic prompt caching reduces repeated token cost by ~50%.",
      current_cost: "34.00",
      expected_saving: "17.00",
      quality_impact: "NEGLIGIBLE",
      latency_impact: "FASTER",
      confidence: 0.92,
      evidence: { cached_token_potential: 1800000 },
    },
    {
      id: "rec-03",
      organization_id: "org-primary",
      recommendation_type: "REDUCE_CONTEXT",
      status: "OPEN",
      title: "Prune RAG Document Chunk Context",
      description: "Top-K retrieval currently returns 15 chunks per query where relevance drops below 0.65 after chunk 5. Pruning to 5 chunks saves ~30% token transfer.",
      current_cost: "24.00",
      expected_saving: "7.20",
      quality_impact: "NEGLIGIBLE",
      latency_impact: "FASTER",
      confidence: 0.82,
      evidence: { avg_chunks_returned: 15, recommended_chunks: 5 },
    },
  ];
}

export default function FinOpsRecommendationsPage() {
  const [recommendations, setRecommendations] = useState<OptimizationRecommendation[]>([]);

  useEffect(() => {
    async function loadRecs() {
      try {
        const res = await fetch("/api/v1/finops/recommendations");
        if (res.ok) {
          const data = await res.json();
          setRecommendations(data.items || getMockRecommendations());
        } else {
          setRecommendations(getMockRecommendations());
        }
      } catch {
        setRecommendations(getMockRecommendations());
      }
    }
    loadRecs();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-purple-500" />
          <h1 className="text-2xl font-bold tracking-tight">AI Cost Optimization Recommendations</h1>
        </div>
        <p className="text-xs text-muted-foreground">
          Evidence-backed efficiency proposals: model downgrades, prompt caching ROI, and context minimization without degrading quality.
        </p>
      </div>

      <FinOpsNav />

      <div className="space-y-4">
        {recommendations.map((rec) => (
          <div key={rec.id} className="rounded-xl border border-border bg-card p-5 space-y-3 shadow-sm">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/10 text-purple-500 border border-purple-500/20">
                {rec.recommendation_type}
              </span>
              <span className="text-xs font-bold text-emerald-500">
                Save ~${Number(rec.expected_saving).toFixed(2)}/mo
              </span>
            </div>

            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-foreground">{rec.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{rec.description}</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2 text-xs border-t border-border">
              <div>
                <span className="text-muted-foreground block text-[10px]">Current Incurred Cost</span>
                <span className="font-mono text-foreground">${Number(rec.current_cost).toFixed(2)}/mo</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Quality Risk</span>
                <span className="text-emerald-500 font-semibold">{rec.quality_impact}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Latency Impact</span>
                <span className="text-blue-500 font-semibold">{rec.latency_impact}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[10px]">Confidence Level</span>
                <span className="font-semibold text-foreground">{(rec.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
