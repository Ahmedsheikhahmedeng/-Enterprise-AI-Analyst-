"use client";

import React, { useState, useEffect } from "react";
import { AlertOctagon } from "lucide-react";
import { SecurityNav } from "@/components/compliance/security-nav";
import { SecurityFinding } from "@/types/compliance";

function getMockFindings(): SecurityFinding[] {
  return [
    {
      id: "find-001",
      control_id: "ctrl-sec-001",
      severity: "HIGH",
      status: "OPEN",
      title: "Potential hardcoded secret candidate in legacy migration script",
      description: "Gitleaks detected entropy match in tests/migrations/fixture.json.",
      source: "gitleaks",
      owner: "security-team",
      first_detected_at: new Date().toISOString(),
      last_detected_at: new Date().toISOString(),
    },
    {
      id: "find-002",
      control_id: "ctrl-data-001",
      severity: "MEDIUM",
      status: "ACCEPTED_RISK",
      title: "Permissive CORS origin allowed for localhost staging endpoint",
      description: "Bandit flagged B101 on test server configuration.",
      source: "bandit",
      owner: "platform-team",
      first_detected_at: new Date().toISOString(),
      last_detected_at: new Date().toISOString(),
      risk_acceptances: [
        {
          id: "ra-001",
          finding_id: "find-002",
          reason: "Staging internal test environment only.",
          accepted_by: "sec-admin@enterprise.com",
          expires_at: new Date(Date.now() + 86400000 * 30).toISOString(),
          active: true,
          created_at: new Date().toISOString(),
        },
      ],
    },
  ];
}

export default function SecurityFindingsPage() {
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<SecurityFinding | null>(null);
  const [reason, setReason] = useState<string>("");
  const [approvalId, setApprovalId] = useState<string>("");
  const [submittingRisk, setSubmittingRisk] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    async function loadFindings() {
      try {
        const res = await fetch("/api/v1/compliance/findings");
        if (res.ok) {
          const data = await res.json();
          setFindings(data);
        } else {
          setFindings(getMockFindings());
        }
      } catch {
        setFindings(getMockFindings());
      }
    }
    loadFindings();
  }, []);

  async function handleAcceptRisk(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFinding) return;
    setSubmittingRisk(true);
    setErrorMsg(null);

    try {
      const expiry = new Date(Date.now() + 86400000 * 30).toISOString();
      const res = await fetch(`/api/v1/compliance/findings/${selectedFinding.id}/risk-acceptance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason,
          expires_at: expiry,
          privileged_approval_id: approvalId || undefined,
        }),
      });

      if (res.ok) {
        setSelectedFinding(null);
        setReason("");
        setApprovalId("");
        const refreshed = await fetch("/api/v1/compliance/findings");
        if (refreshed.ok) {
          setFindings(await refreshed.json());
        }
      } else {
        const data = await res.json();
        setErrorMsg(data.detail || "Failed to submit risk acceptance.");
      }
    } catch {
      setErrorMsg("Network error submitting risk acceptance.");
    } finally {
      setSubmittingRisk(false);
    }
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <AlertOctagon className="h-5 w-5 text-rose-500" />
            Security Findings & Risk Acceptance
          </h1>
          <p className="text-xs text-muted-foreground">
            Aggregated vulnerability findings from Bandit, pip-audit, Gitleaks, and static analysis scanners.
          </p>
        </div>
      </div>

      <SecurityNav />

      {/* Findings List */}
      <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
        <table className="w-full text-left text-xs">
          <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
            <tr>
              <th className="p-3">Severity</th>
              <th className="p-3">Title & Source</th>
              <th className="p-3">Control</th>
              <th className="p-3">Status</th>
              <th className="p-3">First Detected</th>
              <th className="p-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {findings.map((f) => {
              const sevColor =
                f.severity === "CRITICAL"
                  ? "bg-rose-500/10 text-rose-600 border-rose-500/30"
                  : f.severity === "HIGH"
                  ? "bg-amber-500/10 text-amber-600 border-amber-500/30"
                  : "bg-blue-500/10 text-blue-600 border-blue-500/30";

              return (
                <tr key={f.id} className="hover:bg-muted/30 transition-colors">
                  <td className="p-3">
                    <span
                      className={`inline-flex items-center rounded px-2 py-0.5 text-[10px] font-bold border ${sevColor}`}
                    >
                      {f.severity}
                    </span>
                  </td>
                  <td className="p-3">
                    <div className="font-semibold text-foreground">{f.title}</div>
                    <div className="text-[11px] text-muted-foreground font-mono">
                      Source: {f.source} | {f.description}
                    </div>
                  </td>
                  <td className="p-3 font-mono text-[11px] text-muted-foreground">
                    {f.control_id || "N/A"}
                  </td>
                  <td className="p-3">
                    <span className="font-medium text-foreground text-[11px]">
                      {f.status}
                    </span>
                  </td>
                  <td className="p-3 text-[11px] text-muted-foreground">
                    {new Date(f.first_detected_at).toLocaleDateString()}
                  </td>
                  <td className="p-3 text-right">
                    {f.status !== "ACCEPTED_RISK" && f.status !== "RESOLVED" && (
                      <button
                        onClick={() => setSelectedFinding(f)}
                        className="rounded bg-muted px-2.5 py-1 text-[11px] font-medium text-foreground hover:bg-accent transition"
                      >
                        Accept Risk
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Risk Acceptance Modal */}
      {selectedFinding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-border bg-card p-5 shadow-lg space-y-4">
            <div className="border-b border-border pb-2">
              <h3 className="text-sm font-bold text-foreground">
                Accept Risk for Finding
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                {selectedFinding.title} ({selectedFinding.severity})
              </p>
            </div>

            {errorMsg && (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2.5 text-xs text-rose-600">
                {errorMsg}
              </div>
            )}

            <form onSubmit={handleAcceptRisk} className="space-y-3 text-xs">
              <div>
                <label className="font-semibold text-foreground">
                  Business Justification
                </label>
                <textarea
                  required
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain compensating controls and reason for risk acceptance..."
                  className="w-full mt-1 rounded-lg border border-border bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              {selectedFinding.severity === "CRITICAL" && (
                <div className="space-y-1">
                  <label className="font-semibold text-rose-500">
                    Privileged Governance Approval ID (Mandatory for CRITICAL)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. app-req-12345"
                    value={approvalId}
                    onChange={(e) => setApprovalId(e.target.value)}
                    className="w-full rounded-lg border border-border bg-background p-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono text-[11px]"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    Accepting critical risk requires dual-signoff via Governance Approval FSM.
                  </p>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 border-t border-border pt-3">
                <button
                  type="button"
                  onClick={() => setSelectedFinding(null)}
                  className="rounded px-3 py-1.5 text-xs text-muted-foreground hover:bg-muted"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submittingRisk}
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {submittingRisk ? "Submitting..." : "Confirm Acceptance"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
