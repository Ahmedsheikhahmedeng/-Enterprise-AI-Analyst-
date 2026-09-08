"use client";

import React, { useState } from "react";
import { ApprovalItem } from "@/types/platform";
import { useAuth } from "@/features/auth/auth-context";
import { useLanguage } from "@/contexts/language-context";
import { ApprovalDialog } from "./approval-dialog";
import { CheckCircle2, XCircle, Clock, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";

interface ApprovalsListProps {
  items: ApprovalItem[];
  onResolve: (id: string, decision: "APPROVED" | "REJECTED", comment?: string) => Promise<void>;
}

export function ApprovalsList({ items, onResolve }: ApprovalsListProps) {
  const { canApprove } = useAuth();
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [selectedItem, setSelectedItem] = useState<ApprovalItem | null>(null);
  const [filter, setFilter] = useState<string>("ALL");

  const filteredItems = items.filter((item) => {
    if (filter === "ALL") return true;
    return item.status === filter;
  });

  const getRiskBadge = (level: string) => {
    switch (level) {
      case "CRITICAL":
        return "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30";
      case "HIGH":
        return "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30";
      case "MEDIUM":
        return "bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30";
      default:
        return "bg-muted text-muted-foreground border-border";
    }
  };

  const getRiskLabel = (level: string) => {
    if (!isTr) return `${level} RISK`;
    switch (level) {
      case "CRITICAL": return "KRİTİK RİSK";
      case "HIGH": return "YÜKSEK RİSK";
      case "MEDIUM": return "ORTA RİSK";
      default: return `${level} RİSK`;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "APPROVED":
        return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case "REJECTED":
        return <XCircle className="h-4 w-4 text-destructive" />;
      default:
        return <Clock className="h-4 w-4 text-amber-500 animate-pulse" />;
    }
  };

  const TABS = [
    { key: "ALL", label: isTr ? "Tümü" : "ALL" },
    { key: "PENDING", label: isTr ? "Beklemede" : "PENDING" },
    { key: "APPROVED", label: isTr ? "Onaylandı" : "APPROVED" },
    { key: "REJECTED", label: isTr ? "Reddedildi" : "REJECTED" },
  ];

  return (
    <div className="space-y-4">
      {/* Filter Tabs */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1 bg-muted/60 p-1 rounded-lg text-xs">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`px-3 py-1 rounded-md font-medium transition-all ${
                filter === tab.key
                  ? "bg-background text-foreground shadow-xs font-semibold"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <span className="text-xs text-muted-foreground">
          {filteredItems.length} {isTr ? "kayıt bulundu" : "records found"}
        </span>
      </div>

      {/* Approvals Table / Card Grid */}
      {filteredItems.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border/80 p-8 text-center text-xs text-muted-foreground">
          {isTr ? "Seçili filtre altında onay kaydı bulunamadı." : "No approval items found under current filter."}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => (
            <div
              key={item.id}
              className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-xs hover:border-border/80 transition-all"
            >
              <div className="flex items-start gap-3">
                <div className="mt-0.5">{getStatusIcon(item.status)}</div>
                <div className="space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">
                      {item.action_type}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold ${getRiskBadge(
                        item.risk_level
                      )}`}
                    >
                      {getRiskLabel(item.risk_level)}
                    </span>
                    <span className="text-xs font-mono text-muted-foreground">
                      ID: {item.id.slice(0, 8)}...
                    </span>
                  </div>

                  <p className="text-xs text-muted-foreground">
                    {item.reason || (isTr ? "Eylem hassas yönetişim güvenlik kontrolünü tetikledi." : "Action triggered sensitive governance checkpoint.")}
                  </p>

                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground pt-1">
                    <span>{isTr ? "Talep Tarihi:" : "Requested:"} {formatDate(item.created_at)}</span>
                    {item.expires_at && <span>{isTr ? "Bitiş Tarihi:" : "Expires:"} {formatDate(item.expires_at)}</span>}
                    {item.requested_by && <span>{isTr ? "Talep Eden:" : "By:"} {item.requested_by}</span>}
                  </div>
                </div>
              </div>

              {/* Action Button for Authorized Users */}
              {item.status === "PENDING" && canApprove && (
                <Button
                  size="sm"
                  onClick={() => setSelectedItem(item)}
                  className="h-8 gap-1.5 text-xs font-semibold shrink-0"
                >
                  <AlertTriangle className="h-3.5 w-3.5" />
                  <span>{isTr ? "Kararı İncele" : "Review Decision"}</span>
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Decision Dialog */}
      <ApprovalDialog
        item={selectedItem}
        open={!!selectedItem}
        onClose={() => setSelectedItem(null)}
        onResolve={onResolve}
      />
    </div>
  );
}
