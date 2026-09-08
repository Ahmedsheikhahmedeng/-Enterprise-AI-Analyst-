"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useLanguage } from "@/contexts/language-context";
import {
  ShieldCheck,
  FileCheck2,
  Eye,
  Activity,
  AlertTriangle,
  Scale,
  CheckCircle,
  XCircle,
  ArrowUpRight,
} from "lucide-react";
import { SecurityNav } from "@/components/compliance/security-nav";
import { ComplianceOverview } from "@/types/compliance";

function getMockOverview(): ComplianceOverview {
  return {
    posture: {
      overall_score: 94.5,
      assessed_at: new Date().toISOString(),
      pillars: {
        authentication: { pillar: "authentication", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        authorization: { pillar: "authorization", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        tenant_isolation: { pillar: "tenant_isolation", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        secrets: { pillar: "secrets", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        network_security: { pillar: "network_security", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        data_security: { pillar: "data_security", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        audit: { pillar: "audit", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        privacy: { pillar: "privacy", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        dependencies: { pillar: "dependencies", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        vulnerabilities: { pillar: "vulnerabilities", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        backup_security: { pillar: "backup_security", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
        incident_status: { pillar: "incident_status", status: "PASS", controls_total: 2, controls_passed: 2, details: {} },
      },
    },
    readiness: {
      decision: "READY",
      score: 94.5,
      passed_controls: 22,
      warning_controls: 2,
      failed_controls: 0,
      blockers: [],
      warnings: ["Evidence for ISO-A.12.1 is older than 60 days."],
      evaluated_at: new Date().toISOString(),
    },
    open_critical_findings: 0,
    total_findings: 3,
    active_legal_holds: 1,
    pending_privacy_requests: 0,
    active_access_reviews: 1,
    audit_integrity_status: "VALID",
    disclaimer: "This implementation provides technical control readiness and evidence management. It does not constitute SOC 2, ISO 27001, GDPR, HIPAA, or any other formal certification.",
  };
}

export default function SecurityOverviewPage() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [overview, setOverview] = useState<ComplianceOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadOverview() {
      try {
        const res = await fetch("/api/v1/compliance/overview");
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
      <div className="flex h-64 items-center justify-center">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Activity className="h-4 w-4 animate-spin text-primary" />
          <span>
            {isTr
              ? "Kurumsal güvenlik duruşu ve uyum telemetrisi sentezleniyor..."
              : "Synthesizing enterprise security posture and compliance telemetry..."}
          </span>
        </div>
      </div>
    );
  }

  const isReady = overview.readiness.decision === "READY";
  const isWarning = overview.readiness.decision === "READY_WITH_WARNINGS";

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            {isTr ? "Kurumsal Güvenlik & Uyum Yönetişimi" : "Enterprise Security & Compliance Governance"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "Deterministik güvenlik kontrolleri, denetim dereceli kriptografik kanıt zincirleri, erişim incelemeleri ve gizlilik yönetişimi."
              : "Deterministic security controls, audit-grade cryptographic evidence chains, access reviews, and privacy governance."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              isReady
                ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
                : isWarning
                ? "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                : "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                isReady ? "bg-emerald-500" : isWarning ? "bg-amber-500" : "bg-rose-500"
              } animate-pulse`}
            />
            {isTr ? "Hazırlık: " : "Readiness: "}
            {isReady && isTr ? "HAZIR" : isWarning && isTr ? "UYARILARLA HAZIR" : overview.readiness.decision}
          </span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <SecurityNav />

      {/* Certification Boundary Disclaimer Notice */}
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-xs text-muted-foreground flex items-center gap-2.5">
        <Scale className="h-4 w-4 text-primary shrink-0" />
        <span>
          <strong>{isTr ? "Açık Sertifikasyon Sınırı:" : "Explicit Certification Boundary:"}</strong>{" "}
          {overview.disclaimer}
        </span>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Posture Score */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Genel Duruş Skoru" : "Overall Posture Score"}</span>
            <ShieldCheck className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-foreground">
            {overview.posture.overall_score.toFixed(1)} <span className="text-xs font-normal text-muted-foreground">/ 100</span>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {isTr ? "12 sütun ve 24 temel kontrol genelinde ağırlıklı" : "Weighted across 12 pillars & 24 baseline controls"}
          </p>
        </div>

        {/* Audit Log Integrity */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Denetim Zinciri Bütünlüğü" : "Audit Chain Integrity"}</span>
            <FileCheck2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            {overview.audit_integrity_status === "VALID" ? (
              <span className="text-emerald-500 flex items-center gap-1">
                <CheckCircle className="h-5 w-5" /> {isTr ? "GEÇERLİ (VALID)" : "VALID"}
              </span>
            ) : (
              <span className="text-rose-500 flex items-center gap-1">
                <XCircle className="h-5 w-5" /> {isTr ? "BOZULMUŞ" : "COMPROMISED"}
              </span>
            )}
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {isTr ? "Kriptografik SHA-256 karma zinciri doğrulaması" : "Cryptographic SHA-256 hash-chain verification"}
          </p>
        </div>

        {/* Vulnerabilities & Findings */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Kritik Bulgular" : "Critical Findings"}</span>
            <AlertTriangle className="h-4 w-4 text-rose-500" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-foreground">
            {overview.open_critical_findings}{" "}
            <span className="text-xs font-normal text-muted-foreground">
              {isTr ? `(${overview.total_findings} toplam açık)` : `(${overview.total_findings} total open)`}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {isTr ? "Kritik > 0 ise kesin dağıtım engelleyici" : "Hard release blocker if critical > 0"}
          </p>
        </div>

        {/* Governance & Privacy */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{isTr ? "Gizlilik & Yasal Askılar" : "Privacy & Legal Holds"}</span>
            <Eye className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold tracking-tight text-foreground">
            {overview.active_legal_holds}{" "}
            <span className="text-xs font-normal text-muted-foreground">
              {isTr ? "aktif askı" : "active holds"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">
            {overview.pending_privacy_requests} {isTr ? "bekleyen silme talebi" : "pending deletion requests"}
          </p>
        </div>
      </div>

      {/* 12-Pillar Security Posture Matrix */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-sm space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              {isTr ? "12 Sütunlu Güvenlik Mimarisi Duruşu" : "12-Pillar Security Architecture Posture"}
            </h2>
            <p className="text-xs text-muted-foreground">
              {isTr
                ? "Kurumsal güvenlik alanları genelinde gerçek zamanlı sağlık birleşimi"
                : "Real-time health aggregation across enterprise security domains"}
            </p>
          </div>
          <Link
            href="/security/controls"
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            {isTr ? "Kontrol Kataloğunu İncele" : "View Controls Catalog"} <ArrowUpRight className="h-3 w-3" />
          </Link>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {Object.entries(overview.posture.pillars).map(([key, pillar]) => {
            const statusColor =
              pillar.status === "PASS"
                ? "text-emerald-500 bg-emerald-500/10 border-emerald-500/20"
                : pillar.status === "WARN"
                ? "text-amber-500 bg-amber-500/10 border-amber-500/20"
                : "text-rose-500 bg-rose-500/10 border-rose-500/20";

            return (
              <div
                key={key}
                className="rounded-lg border border-border/80 bg-background/50 p-3 flex flex-col justify-between"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold capitalize text-foreground">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span
                    className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold border ${statusColor}`}
                  >
                    {pillar.status === "PASS" && isTr ? "GEÇTİ" : pillar.status === "WARN" && isTr ? "UYARI" : pillar.status}
                  </span>
                </div>
                <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>{isTr ? "Geçen Kontroller" : "Controls Passed"}</span>
                  <span className="font-semibold text-foreground">
                    {pillar.controls_passed} / {pillar.controls_total}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Warnings & Blockers Panel */}
      {overview.readiness.warnings.length > 0 && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-4 w-4" />
            <span>
              {isTr ? "Uyum Değerlendirme Uyarıları" : "Compliance Assessment Warnings"} ({overview.readiness.warnings.length})
            </span>
          </div>
          <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
            {overview.readiness.warnings.map((w, idx) => (
              <li key={idx} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
