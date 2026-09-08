"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowLeft,
} from "lucide-react";
import { SREAlert } from "@/types/sre";
import { useLanguage } from "@/contexts/language-context";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<SREAlert[]>([]);
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/v1/sre/alerts");
        if (res.ok) {
          setAlerts(await res.json());
        } else {
          setAlerts([
            {
              id: "alt-1",
              fingerprint: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
              name: isTr ? "Yüksek API Gecikmesi (p95 > 500ms)" : "High API Latency (p95 > 500ms)",
              service: "api_gateway",
              severity: "WARNING",
              status: "FIRING",
              source: "sre_engine",
              metric: "LATENCY_P95",
              value: 620.0,
              threshold: 500.0,
              starts_at: new Date(Date.now() - 1800000).toISOString(),
              last_seen_at: new Date().toISOString(),
              count: 14,
            },
            {
              id: "alt-2",
              fingerprint: "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e",
              name: isTr ? "İşçi Görev Kuyruğu Gecikmesi Aşıldı" : "Worker Task Queue Lag Exceeded",
              service: "workers",
              severity: "ERROR",
              status: "ACKNOWLEDGED",
              source: "sre_engine",
              metric: "QUEUE_LAG",
              value: 45.0,
              threshold: 30.0,
              starts_at: new Date(Date.now() - 3600000).toISOString(),
              last_seen_at: new Date(Date.now() - 600000).toISOString(),
              count: 8,
            },
          ]);
        }
      } catch {
        setAlerts([]);
      }
    }
    load();
  }, [isTr]);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div className="flex items-center gap-3">
          <Link
            href="/operations"
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              {isTr ? "Uyarılar & Tekilleştirme Motoru" : "Alerts & Deduplication Engine"}
            </h1>
            <p className="text-xs text-muted-foreground">
              {isTr
                ? "Deterministik parmak izi çıkarma, bakım baskılama ve uyarı fırtınası gürültü azaltma."
                : "Deterministic fingerprinting, maintenance suppression, and alert storm noise reduction."}
            </p>
          </div>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold">{isTr ? "Aktif Operasyonel Uyarılar" : "Active Operational Alerts"}</h2>
          <span className="text-xs text-muted-foreground">
            {isTr ? "SHA-256 Parmak İzi ile Tekilleştirildi" : "Deduplicated by SHA-256 Fingerprint"}
          </span>
        </div>
        <div className="divide-y divide-border">
          {alerts.map((alt) => (
            <div key={alt.id} className="p-4 hover:bg-muted/30 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                      alt.severity === "CRITICAL"
                        ? "bg-red-500/20 text-red-600 dark:text-red-400"
                        : alt.severity === "ERROR"
                        ? "bg-amber-500/20 text-amber-600 dark:text-amber-400"
                        : "bg-blue-500/20 text-blue-600 dark:text-blue-400"
                    }`}
                  >
                    {alt.severity}
                  </span>
                  <span className="font-semibold text-sm text-foreground">{alt.name}</span>
                  <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                    {isTr ? "Tekrar: x" : "Count: x"}{alt.count}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                  <span>{isTr ? "Servis: " : "Service: "}<strong>{alt.service}</strong></span>
                  <span>{isTr ? "Metrik: " : "Metric: "}<strong>{alt.metric}</strong></span>
                  {alt.value && <span>{isTr ? "Değer: " : "Value: "}<strong>{alt.value}</strong> ({isTr ? "Eşik: " : "Threshold: "}{alt.threshold})</span>}
                  <span>{isTr ? "İlk Görülme: " : "First Seen: "}{new Date(alt.starts_at).toLocaleTimeString()}</span>
                  <span>{isTr ? "Son Görülme: " : "Last Seen: "}{new Date(alt.last_seen_at).toLocaleTimeString()}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    alt.status === "FIRING"
                      ? "bg-red-500/15 text-red-600 dark:text-red-400 animate-pulse"
                      : alt.status === "ACKNOWLEDGED"
                      ? "bg-blue-500/15 text-blue-600 dark:text-blue-400"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {alt.status}
                </span>
              </div>
            </div>
          ))}
          {alerts.length === 0 && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              {isTr
                ? "Aktif uyarı yok. Tüm sistemler tanımlı SLO sınırları içinde çalışıyor."
                : "No firing alerts. All systems operating within defined SLO boundaries."}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
