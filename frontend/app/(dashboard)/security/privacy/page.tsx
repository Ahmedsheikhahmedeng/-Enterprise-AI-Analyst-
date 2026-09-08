"use client";

import React, { useState, useEffect } from "react";
import {
  EyeOff,
  Scale,
  Plus,
  Lock,
} from "lucide-react";
import { SecurityNav } from "@/components/compliance/security-nav";
import { LegalHold, PrivacyRequest } from "@/types/compliance";

function getMockHolds(): LegalHold[] {
  return [
    {
      id: "hold-001",
      name: "Litigation Hold - Project Alpha Investigation",
      reason: "Active legal preservation order covering all analytical reports and query execution logs.",
      created_by: "legal-counsel@enterprise.com",
      active: true,
      starts_at: new Date().toISOString(),
      resources: ["datasets/*", "reports/*"],
    },
  ];
}

function getMockPrivacyRequests(): PrivacyRequest[] {
  return [
    {
      id: "pr-001",
      user_id: "u-998",
      request_type: "RIGHT_TO_DELETE",
      requested_by: "data-subject@example.com",
      status: "REVIEW_REQUIRED",
      resources: ["user_profile", "chat_history"],
      created_at: new Date().toISOString(),
      notes: "Subject requested erasure under GDPR Article 17. Multi-signature governance approval required.",
    },
  ];
}

export default function PrivacyPage() {
  const [legalHolds, setLegalHolds] = useState<LegalHold[]>([]);
  const [privacyRequests, setPrivacyRequests] = useState<PrivacyRequest[]>([]);
  const [showHoldModal, setShowHoldModal] = useState<boolean>(false);
  const [holdName, setHoldName] = useState<string>("");
  const [holdReason, setHoldReason] = useState<string>("");
  const [holdResources, setHoldResources] = useState<string>("*");

  useEffect(() => {
    async function loadData() {
      try {
        const [holdRes, privRes] = await Promise.all([
          fetch("/api/v1/compliance/legal-holds"),
          fetch("/api/v1/compliance/privacy-requests"),
        ]);

        if (holdRes.ok) setLegalHolds(await holdRes.json());
        else setLegalHolds(getMockHolds());

        if (privRes.ok) setPrivacyRequests(await privRes.json());
        else setPrivacyRequests(getMockPrivacyRequests());
      } catch {
        setLegalHolds(getMockHolds());
        setPrivacyRequests(getMockPrivacyRequests());
      }
    }
    loadData();
  }, []);

  async function handleCreateHold(e: React.FormEvent) {
    e.preventDefault();
    try {
      const res = await fetch("/api/v1/compliance/legal-holds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: holdName,
          reason: holdReason,
          resources: holdResources.split(",").map((s) => s.trim()),
        }),
      });
      if (res.ok) {
        setShowHoldModal(false);
        setHoldName("");
        setHoldReason("");
        const refreshed = await fetch("/api/v1/compliance/legal-holds");
        if (refreshed.ok) {
          setLegalHolds(await refreshed.json());
        }
      }
    } catch {
      // Handle error
    }
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <EyeOff className="h-5 w-5 text-primary" />
            Privacy Governance & Legal Holds
          </h1>
          <p className="text-xs text-muted-foreground">
            Enforce GDPR / CCPA right-to-delete workflows, automated PII masking, and tamper-resistant legal preservation holds.
          </p>
        </div>
        <button
          onClick={() => setShowHoldModal(true)}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition"
        >
          <Plus className="h-3.5 w-3.5" />
          Create Legal Hold
        </button>
      </div>

      <SecurityNav />

      {/* Active Legal Holds Section */}
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Scale className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-bold text-foreground">
            Active Legal Holds ({legalHolds.length})
          </h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Any resources covered under an active Legal Hold are strictly frozen from automated retention expiration or privacy deletion.
        </p>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {legalHolds.map((hold) => (
            <div key={hold.id} className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs text-foreground">{hold.name}</span>
                <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-500 border border-emerald-500/20">
                  Active Hold
                </span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                {hold.reason}
              </p>
              <div className="border-t border-border pt-2 text-[11px] text-muted-foreground space-y-1">
                <div>Created by: <span className="text-foreground font-mono">{hold.created_by}</span></div>
                <div>Protected resources: <span className="font-mono text-primary">{hold.resources.join(", ")}</span></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Privacy Requests (Right to Delete) */}
      <div className="space-y-3 pt-4 border-t border-border">
        <div className="flex items-center gap-2">
          <Lock className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-bold text-foreground">
            Data Subject Privacy Requests (Right-to-Delete)
          </h2>
        </div>
        <p className="text-xs text-muted-foreground">
          Right-to-delete requests undergo multi-stage review (REQUESTED &rarr; REVIEW_REQUIRED &rarr; APPROVED &rarr; EXECUTED). Never destructively executed without explicit governance authorization.
        </p>

        <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
              <tr>
                <th className="p-3">Request ID</th>
                <th className="p-3">Requested By</th>
                <th className="p-3">Type</th>
                <th className="p-3">Target Resources</th>
                <th className="p-3">Status</th>
                <th className="p-3">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border font-mono text-[11px]">
              {privacyRequests.map((req) => (
                <tr key={req.id} className="hover:bg-muted/30">
                  <td className="p-3 text-primary font-bold">{req.id}</td>
                  <td className="p-3 text-foreground font-sans">{req.requested_by}</td>
                  <td className="p-3 text-muted-foreground">{req.request_type}</td>
                  <td className="p-3 text-muted-foreground">{req.resources.join(", ")}</td>
                  <td className="p-3">
                    <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[10px] font-bold text-amber-600 border border-amber-500/20 font-sans">
                      {req.status}
                    </span>
                  </td>
                  <td className="p-3 text-muted-foreground font-sans text-xs">{req.notes || "None"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Legal Hold Modal */}
      {showHoldModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-lg space-y-4">
            <div className="border-b border-border pb-2">
              <h3 className="text-sm font-bold text-foreground">Create Preservation Legal Hold</h3>
              <p className="text-xs text-muted-foreground">Freezes deletion eligibility across selected tenant resources.</p>
            </div>

            <form onSubmit={handleCreateHold} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-foreground">Hold Name / Case Reference</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Subpoena 2026-B Audit Preservation"
                  value={holdName}
                  onChange={(e) => setHoldName(e.target.value)}
                  className="w-full mt-1 rounded-lg border border-border bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div>
                <label className="font-semibold text-foreground">Legal Justification / Scope</label>
                <textarea
                  required
                  rows={3}
                  placeholder="Document legal reason, court order, or internal inquiry..."
                  value={holdReason}
                  onChange={(e) => setHoldReason(e.target.value)}
                  className="w-full mt-1 rounded-lg border border-border bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div>
                <label className="font-semibold text-foreground">Target Resource Patterns (comma-separated)</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. datasets/*, audit_events/* or *"
                  value={holdResources}
                  onChange={(e) => setHoldResources(e.target.value)}
                  className="w-full mt-1 rounded-lg border border-border bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
                <button
                  type="button"
                  onClick={() => setShowHoldModal(false)}
                  className="rounded px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90"
                >
                  Issue Legal Hold
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
