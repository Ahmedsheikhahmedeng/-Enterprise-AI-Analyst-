"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  BookOpen,
  ArrowLeft,
  ShieldCheck,
  Terminal,
  AlertOctagon,
} from "lucide-react";
import { Runbook } from "@/types/sre";
import { useLanguage } from "@/contexts/language-context";

export default function RunbooksPage() {
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/v1/sre/runbooks");
        if (res.ok) {
          setRunbooks(await res.json());
        } else {
          setRunbooks([
            {
              id: "rb-1",
              name: isTr ? "PostgreSQL Yüksek Gecikme & Bağlantı Havuzu Tükenmesi" : "PostgreSQL High Latency & Pool Exhaustion",
              description: isTr
                ? "Okuma/yazma bağlantı havuzu doygunluğu ve sorgu kilidi duraklamaları için tanısal triyaj."
                : "Diagnostic triage for read/write connection pool saturation and query lock stalls.",
              service: "database",
              trigger: "DB_POOL_SATURATION > 90% for 3 minutes",
              symptoms: [
                "API response latency spike (p95 > 800ms)",
                "Connection timeout errors on FastAPI workers",
                "Asyncpg PoolTimeout exceptions in logs",
              ],
              diagnostic_steps: [
                "Inspect active connection count: SELECT count(*) FROM pg_stat_activity WHERE state = 'active'",
                "Check for long-running blocking queries: SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY 2 DESC LIMIT 5",
                "Verify Redis cache hit ratio to ensure reads are not all falling through to PostgreSQL",
              ],
              safe_actions: isTr
                ? [
                    "Boştaki arka plan bağlantı havuzu tahsislerini güvenli şekilde geri dönüştürün",
                    "Redis okuma kopyalarında geçici okuma sorgusu önbelleğe almayı etkinleştirin",
                    "Doygunluk 10 dakikayı aşarsa Olay Yöneticisini bilgilendirin",
                  ]
                : [
                    "Gracefully recycle idle background connection pool allocations",
                    "Enable temporary read query caching on Redis read replicas",
                    "Notify Incident Commander if saturation persists beyond 10 minutes",
                  ],
              rollback_notes: "Revert any temporary read cache TTL overrides via configuration",
              owner: "sre-database-team",
              version: 2,
              is_published: true,
            },
            {
              id: "rb-2",
              name: isTr ? "İşçi Görev Kuyruğu Gecikme Giderme" : "Worker Task Queue Lag Remediation",
              description: isTr
                ? "Eşzamansız iş yüklerini kaybetmeden kuyruk birikmesini temizleme prosedürleri."
                : "Procedures for clearing queue backlog without losing asynchronous job payloads.",
              service: "workers",
              trigger: "QUEUE_LAG > 60s or PENDING_JOBS > 2000",
              symptoms: [
                "Delayed analysis report delivery",
                "Dataset ingestion jobs lingering in PENDING status",
              ],
              diagnostic_steps: [
                "Check active worker container health and memory usage",
                "Inspect Dead Letter Queue (DLQ) for poison pills",
                "Verify Redis queue depth key: LLEN celery / RQ stream length",
              ],
              safe_actions: isTr
                ? [
                    "Arka plan işçi kopyalarını onaylı konteyner limitleri dahilinde genişletin",
                    "Hatalı DLQ iletilerini ikincil inceleme kuyruğuna izole edin",
                  ]
                : [
                    "Scale out background worker replicas within approved container limits",
                    "Isolate failed DLQ messages to auxiliary inspection queue",
                  ],
              rollback_notes: "Scale down auxiliary worker replicas after queue clears",
              owner: "sre-platform-team",
              version: 1,
              is_published: true,
            },
          ]);
        }
      } catch {
        setRunbooks([]);
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
              <BookOpen className="h-5 w-5 text-primary" />
              {isTr ? "Tanı & Müdahale Rehberleri (Runbooks)" : "Diagnostic Runbooks & Safe Actions"}
            </h1>
            <p className="text-xs text-muted-foreground">
              {isTr
                ? "Değiştirilemez sürümlü kılavuzlar. Yıkıcı kabuk ve veritabanı komutları politika gereği kesinlikle yasaktır."
                : "Immutable versioned playbooks. Destructive shell and database commands are strictly prohibited by policy."}
            </p>
          </div>
        </div>
      </div>

      {/* Runbooks List */}
      <div className="grid grid-cols-1 gap-6">
        {runbooks.map((rb) => (
          <div key={rb.id} className="rounded-xl border border-border bg-card p-5 space-y-4 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-border/60 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-semibold text-foreground">{rb.name}</h3>
                  <span className="rounded bg-primary/10 px-2 py-0.5 text-[11px] font-mono font-medium text-primary">
                    v{rb.version} {rb.is_published ? (isTr ? "(Yayınlandı)" : "(Published)") : (isTr ? "(Taslak)" : "(Draft)")}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-0.5">{rb.description}</p>
              </div>
              <div className="text-xs text-muted-foreground">
                {isTr ? "Servis: " : "Service: "}<strong className="text-foreground">{rb.service}</strong> | {isTr ? "Sorumlu: " : "Owner: "}<strong className="text-foreground">{rb.owner}</strong>
              </div>
            </div>

            {/* Trigger condition */}
            <div className="rounded-lg bg-muted/40 p-3 text-xs flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 text-amber-500 shrink-0" />
              <span><strong>{isTr ? "Tetikleyici Uyarı: " : "Trigger Alert: "}</strong>{rb.trigger}</span>
            </div>

            {/* Diagnostics & Safe actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <Terminal className="h-3.5 w-3.5 text-primary" />
                  {isTr ? "Tanılama Adımları (Salt-Okunur)" : "Diagnostic Steps (Read-Only)"}
                </h4>
                <ul className="space-y-1 text-xs text-foreground list-disc list-inside">
                  {rb.diagnostic_steps.map((step, idx) => (
                    <li key={idx} className="leading-relaxed font-mono bg-muted/30 p-1.5 rounded text-[11px]">
                      {step}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                  {isTr ? "Güvenli Eylemler (Yıkıcı Olmayan)" : "Safe Actions (Non-Destructive)"}
                </h4>
                <ul className="space-y-1 text-xs text-foreground list-disc list-inside">
                  {rb.safe_actions.map((act, idx) => (
                    <li key={idx} className="leading-relaxed bg-emerald-500/5 text-emerald-800 dark:text-emerald-300 p-1.5 rounded text-[11px]">
                      {act}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
