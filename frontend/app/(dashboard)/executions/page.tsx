"use client";

import React, { useState } from "react";
import { ExecutionTable } from "@/features/executions/execution-table";
import { useExecutions } from "@/hooks/use-platform";
import { useLanguage } from "@/contexts/language-context";
import { Skeleton } from "@/components/common/skeleton-loader";
import { History } from "lucide-react";

const SAMPLE_EXECUTIONS = [
  {
    execution_id: "7fa1bc82-019a-4c91-9e23-2891bcda4091",
    question: "What are Q3 financial earnings results and operating margins?",
    status: "COMPLETED" as const,
    mode: "AUTO" as const,
    duration_ms: 184.2,
    created_at: "2026-09-07T18:00:00.000Z",
  },
  {
    execution_id: "8ca2bc93-120b-5d02-0f34-3902cdeb5102",
    question: "Export confidential customer PII transaction logs to external S3",
    status: "APPROVAL_REQUIRED" as const,
    mode: "SQL" as const,
    duration_ms: 92.0,
    created_at: "2026-09-07T17:00:00.000Z",
  },
  {
    execution_id: "9db3cd04-231c-6e13-1a45-4013defc6213",
    question: "Cross-correlate churn predictions against Q2 customer contracts",
    status: "COMPLETED" as const,
    mode: "HYBRID" as const,
    duration_ms: 320.5,
    created_at: "2026-09-07T16:00:00.000Z",
  },
];

export default function ExecutionsPage() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [page, setPage] = useState(1);
  const { data, isLoading } = useExecutions({ page, pageSize: 20 });
  const executions = data?.items && data.items.length > 0 ? data.items : SAMPLE_EXECUTIONS;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <History className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            {isTr ? "Çalıştırma Denetim Geçmişi" : "Execution Audit History"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "Tüm kullanıcı ve ajan orkestrasyonlu analitik iş akışlarının değiştirilemez denetim günlüğü."
              : "Immutable log of all user and agent-orchestrated analytical workflows."}
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : (
        <ExecutionTable
          executions={executions}
          page={page}
          totalPages={data?.pagination?.total_pages || 1}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
