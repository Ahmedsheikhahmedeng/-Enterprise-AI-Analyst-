"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ExecutionSummary, ExecutionStatus } from "@/types/platform";
import { useLanguage } from "@/contexts/language-context";
import { formatDate, formatDuration } from "@/lib/utils";
import { CheckCircle2, XCircle, Clock, AlertTriangle, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ExecutionTableProps {
  executions: ExecutionSummary[];
  onPageChange?: (page: number) => void;
  page?: number;
  totalPages?: number;
}

export function ExecutionTable({
  executions,
  onPageChange,
  page = 1,
  totalPages = 1,
}: ExecutionTableProps) {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [modeFilter, setModeFilter] = useState<string>("ALL");

  const filtered = executions.filter((item) => {
    const matchStatus = statusFilter === "ALL" || item.status === statusFilter;
    const matchMode = modeFilter === "ALL" || item.mode === modeFilter;
    return matchStatus && matchMode;
  });

  const getStatusBadge = (status: ExecutionStatus) => {
    switch (status) {
      case "COMPLETED":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3" />
            {isTr ? "TAMAMLANDI" : "COMPLETED"}
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive border border-destructive/20">
            <XCircle className="h-3 w-3" />
            {isTr ? "BAŞARISIZ" : "FAILED"}
          </span>
        );
      case "CANCELLED":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground border border-border">
            {isTr ? "İPTAL EDİLDİ" : "CANCELLED"}
          </span>
        );
      case "APPROVAL_REQUIRED":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <AlertTriangle className="h-3 w-3" />
            {isTr ? "ONAY GEREKİYOR" : "APPROVAL"}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary border border-primary/20">
            <Clock className="h-3 w-3 animate-spin" />
            {isTr ? "ÇALIŞIYOR" : "RUNNING"}
          </span>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by execution status"
            className="h-8 rounded-lg border border-border bg-card px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="ALL">{isTr ? "Tüm Durumlar" : "All Statuses"}</option>
            <option value="COMPLETED">{isTr ? "Tamamlandı" : "Completed"}</option>
            <option value="FAILED">{isTr ? "Başarısız" : "Failed"}</option>
            <option value="APPROVAL_REQUIRED">{isTr ? "Onay Gerekiyor" : "Approval Required"}</option>
            <option value="CANCELLED">{isTr ? "İptal Edildi" : "Cancelled"}</option>
          </select>

          {/* Mode Filter */}
          <select
            value={modeFilter}
            onChange={(e) => setModeFilter(e.target.value)}
            aria-label="Filter by orchestration mode"
            className="h-8 rounded-lg border border-border bg-card px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="ALL">{isTr ? "Tüm Modlar" : "All Modes"}</option>
            <option value="AUTO">{isTr ? "Otomatik (Auto)" : "Auto"}</option>
            <option value="SQL">SQL</option>
            <option value="RAG">RAG</option>
            <option value="HYBRID">{isTr ? "Hibrit (Hybrid)" : "Hybrid"}</option>
            <option value="GRAPH">{isTr ? "Graf (Graph)" : "Graph"}</option>
          </select>
        </div>

        <span className="text-xs text-muted-foreground">
          {isTr ? `${filtered.length} çalıştırma gösteriliyor` : `Showing ${filtered.length} executions`}
        </span>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/50 border-b border-border text-muted-foreground font-medium">
            <tr>
              <th className="p-3.5">{isTr ? "Çalıştırma ID & Sorgu" : "Execution ID & Query"}</th>
              <th className="p-3.5">{isTr ? "Mod" : "Mode"}</th>
              <th className="p-3.5">{isTr ? "Durum" : "Status"}</th>
              <th className="p-3.5">{isTr ? "Süre" : "Duration"}</th>
              <th className="p-3.5">{isTr ? "Zaman Damgası" : "Timestamp"}</th>
              <th className="p-3.5 text-right">{isTr ? "Eylem" : "Action"}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted-foreground">
                  {isTr ? "Mevcut kriterlere uyan çalıştırma kaydı bulunamadı." : "No executions recorded matching current criteria."}
                </td>
              </tr>
            ) : (
              filtered.map((item) => (
                <tr key={item.execution_id} className="hover:bg-muted/30 transition-colors">
                  <td className="p-3.5 max-w-sm">
                    <div className="font-semibold text-foreground truncate">
                      {item.question}
                    </div>
                    <div className="font-mono text-[10px] text-muted-foreground">
                      {item.execution_id}
                    </div>
                  </td>
                  <td className="p-3.5">
                    <span className="rounded bg-muted px-2 py-0.5 font-mono text-[10px] font-semibold text-foreground">
                      {item.mode}
                    </span>
                  </td>
                  <td className="p-3.5">{getStatusBadge(item.status)}</td>
                  <td className="p-3.5 font-mono text-[11px] text-muted-foreground">
                    {formatDuration(item.duration_ms)}
                  </td>
                  <td className="p-3.5 text-muted-foreground text-[11px]">
                    {formatDate(item.created_at)}
                  </td>
                  <td className="p-3.5 text-right">
                    <Link href={`/executions/${item.execution_id}`}>
                      <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs text-primary">
                        <span>{isTr ? "Detaylar" : "Details"}</span>
                        <ExternalLink className="h-3 w-3" />
                      </Button>
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange?.(page - 1)}
          >
            {isTr ? "Önceki" : "Previous"}
          </Button>
          <span className="text-xs text-muted-foreground">
            {isTr ? `Sayfa ${page} / ${totalPages}` : `Page ${page} of ${totalPages}`}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => onPageChange?.(page + 1)}
          >
            {isTr ? "Sonraki" : "Next"}
          </Button>
        </div>
      )}
    </div>
  );
}
