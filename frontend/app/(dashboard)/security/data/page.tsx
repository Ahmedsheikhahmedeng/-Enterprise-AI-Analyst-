"use client";

import React, { useState, useEffect } from "react";
import {
  Database,
  Globe,
  FileSpreadsheet,
} from "lucide-react";
import { SecurityNav } from "@/components/compliance/security-nav";
import { DataClassificationRecord } from "@/types/compliance";

function getMockClassifications(): DataClassificationRecord[] {
  return [
    {
      id: "dc-001",
      resource_type: "dataset",
      resource_id: "ds-customer-churn",
      classification: "CONFIDENTIAL",
      pii_types_detected: ["EMAIL", "PHONE"],
      classified_by: "data-steward@enterprise.com",
      notes: "Contains hashed customer emails. LLM external processing requires pre-approved provider.",
      updated_at: new Date().toISOString(),
    },
    {
      id: "dc-002",
      resource_type: "document",
      resource_id: "doc-payroll-q3",
      classification: "RESTRICTED",
      pii_types_detected: ["PERSON_NAME", "NATIONAL_ID", "BANK_ACCOUNT"],
      classified_by: "hr-admin@enterprise.com",
      notes: "Restricted tier. External LLM and untrusted agent tools strictly blocked.",
      updated_at: new Date().toISOString(),
    },
    {
      id: "dc-003",
      resource_type: "connector",
      resource_id: "conn-public-marketing",
      classification: "PUBLIC",
      pii_types_detected: [],
      classified_by: "marketing-lead@enterprise.com",
      notes: "Public marketing metrics and blog posts.",
      updated_at: new Date().toISOString(),
    },
  ];
}

export default function DataClassificationPage() {
  const [classifications, setClassifications] = useState<DataClassificationRecord[]>([]);

  useEffect(() => {
    async function loadClassifications() {
      try {
        const res = await fetch("/api/v1/compliance/data-classification");
        if (res.ok) {
          const data = await res.json();
          setClassifications(data);
        } else {
          setClassifications(getMockClassifications());
        }
      } catch {
        setClassifications(getMockClassifications());
      }
    }
    loadClassifications();
  }, []);

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            Data Classification & LLM Governance Policies
          </h1>
          <p className="text-xs text-muted-foreground">
            Multi-tier classification dictating LLM model routing, vector embedding permissions, agent tool access, and export boundaries.
          </p>
        </div>
      </div>

      <SecurityNav />

      {/* 5-Tier Policy Reference Matrix */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Platform Data Classification & Handling Guardrails
        </h2>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-5 text-xs">
          {/* PUBLIC */}
          <div className="rounded-lg border border-border/80 bg-background/60 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-foreground">PUBLIC</span>
              <Globe className="h-3.5 w-3.5 text-blue-500" />
            </div>
            <p className="text-[11px] text-muted-foreground">Marketing, docs, public data.</p>
            <div className="text-[10px] space-y-0.5 pt-1 text-muted-foreground border-t border-border">
              <div>LLM: All providers</div>
              <div>Export: Allowed</div>
              <div>Agents: Unrestricted</div>
            </div>
          </div>

          {/* INTERNAL */}
          <div className="rounded-lg border border-border/80 bg-background/60 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-foreground">INTERNAL</span>
              <FileSpreadsheet className="h-3.5 w-3.5 text-emerald-500" />
            </div>
            <p className="text-[11px] text-muted-foreground">Internal operations & telemetry.</p>
            <div className="text-[10px] space-y-0.5 pt-1 text-muted-foreground border-t border-border">
              <div>LLM: All approved</div>
              <div>Export: Org-scoped</div>
              <div>Agents: Allowed</div>
            </div>
          </div>

          {/* CONFIDENTIAL */}
          <div className="rounded-lg border border-border/80 bg-background/60 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-amber-500">CONFIDENTIAL</span>
            </div>
            <p className="text-[11px] text-muted-foreground">Business financial & customer data.</p>
            <div className="text-[10px] space-y-0.5 pt-1 text-muted-foreground border-t border-border">
              <div>LLM: Zero-retention only</div>
              <div>Export: Dual-approval</div>
              <div>Agents: Whitelisted tools</div>
            </div>
          </div>

          {/* RESTRICTED */}
          <div className="rounded-lg border border-border/80 bg-background/60 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-rose-500">RESTRICTED</span>
            </div>
            <p className="text-[11px] text-muted-foreground">Strict secrets, PII, biometric.</p>
            <div className="text-[10px] space-y-0.5 pt-1 text-muted-foreground border-t border-border">
              <div>LLM: Local / on-prem only</div>
              <div>Export: Blocked</div>
              <div>Agents: Local execution</div>
            </div>
          </div>

          {/* SENSITIVE */}
          <div className="rounded-lg border border-border/80 bg-background/60 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-bold text-purple-500">SENSITIVE</span>
            </div>
            <p className="text-[11px] text-muted-foreground">Health, payment card, credentials.</p>
            <div className="text-[10px] space-y-0.5 pt-1 text-muted-foreground border-t border-border">
              <div>LLM: Redaction required</div>
              <div>Export: Prohibited</div>
              <div>Agents: Zero egress</div>
            </div>
          </div>
        </div>
      </div>

      {/* Classified Resources Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
            <tr>
              <th className="p-3">Resource Type</th>
              <th className="p-3">Resource ID</th>
              <th className="p-3">Classification Tier</th>
              <th className="p-3">Detected PII</th>
              <th className="p-3">Classified By</th>
              <th className="p-3">Notes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {classifications.map((r) => {
              const tierColor =
                r.classification === "RESTRICTED"
                  ? "bg-rose-500/10 text-rose-600 border-rose-500/20"
                  : r.classification === "CONFIDENTIAL"
                  ? "bg-amber-500/10 text-amber-600 border-amber-500/20"
                  : r.classification === "SENSITIVE"
                  ? "bg-purple-500/10 text-purple-600 border-purple-500/20"
                  : "bg-emerald-500/10 text-emerald-600 border-emerald-500/20";

              return (
                <tr key={r.id} className="hover:bg-muted/30">
                  <td className="p-3 font-medium capitalize text-foreground">{r.resource_type}</td>
                  <td className="p-3 font-mono text-[11px] text-primary">{r.resource_id}</td>
                  <td className="p-3">
                    <span className={`inline-flex items-center rounded px-2 py-0.5 text-[10px] font-bold border ${tierColor}`}>
                      {r.classification}
                    </span>
                  </td>
                  <td className="p-3">
                    {r.pii_types_detected.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {r.pii_types_detected.map((p, i) => (
                          <span key={i} className="rounded bg-muted px-1.5 py-0.2 text-[10px] font-mono text-foreground">
                            {p}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-muted-foreground text-[11px]">None</span>
                    )}
                  </td>
                  <td className="p-3 text-[11px] text-muted-foreground">{r.classified_by}</td>
                  <td className="p-3 text-muted-foreground text-xs">{r.notes || "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
