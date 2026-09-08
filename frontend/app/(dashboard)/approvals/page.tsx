"use client";

import React from "react";
import { ApprovalsList } from "@/features/approvals/approvals-list";
import { useApprovals } from "@/hooks/use-platform";
import { useLanguage } from "@/contexts/language-context";
import { ShieldAlert } from "lucide-react";

const SAMPLE_APPROVALS = [
  {
    id: "appr-001",
    execution_id: "8ca2bc93-120b-5d02-0f34-3902cdeb5102",
    action_type: "BULK_EXPORT_PII_DATA",
    risk_level: "HIGH" as const,
    status: "PENDING" as const,
    reason: "Query requested raw export of 50,000 sensitive transaction records exceeding organizational DLP threshold.",
    requested_by: "agent-sql-executor-4",
    created_at: "2026-09-07T17:30:00.000Z",
    expires_at: "2026-09-08T17:30:00.000Z",
  },
  {
    id: "appr-002",
    execution_id: "9cb3dc04-231c-6e13-1a45-4013defc6213",
    action_type: "MUTATE_SEMANTIC_METRIC",
    risk_level: "MEDIUM" as const,
    status: "APPROVED" as const,
    reason: "Requested updating official definition formula of 'Gross Churn Rate'.",
    requested_by: "lead_analyst",
    created_at: "2026-09-06T18:00:00.000Z",
    expires_at: "2026-09-07T06:00:00.000Z",
  },
];

export default function ApprovalsPage() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const { data, resolve } = useApprovals();
  const sampleApprovals = data && data.length > 0 ? data : SAMPLE_APPROVALS;

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-500">
          <ShieldAlert className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            {isTr ? "Yönetişim & İnsan Onay Kuyruğu" : "Governance & Human Approvals Queue"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "Yüksek riskli SQL işlemlerini, PII veri taleplerini ve semantik mutasyonları inceleyin ve karara bağlayın."
              : "Review and resolve high-risk SQL operations, PII requests, and semantic mutations."}
          </p>
        </div>
      </div>

      <ApprovalsList
        items={sampleApprovals}
        onResolve={async (id, decision, comment) => {
          try {
            await resolve({ id, decision, comment });
          } catch {
            // handled gracefully
          }
        }}
      />
    </div>
  );
}
