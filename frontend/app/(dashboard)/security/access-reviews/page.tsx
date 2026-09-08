"use client";

import React, { useState, useEffect } from "react";
import {
  Users,
  Play,
  AlertTriangle,
} from "lucide-react";
import { SecurityNav } from "@/components/compliance/security-nav";
import { AccessReview } from "@/types/compliance";

function getMockReviews(): AccessReview[] {
  return [
    {
      id: "ar-001",
      title: "Q3 Enterprise Privileged Access Review",
      initiated_by: "sec-admin@enterprise.com",
      status: "IN_PROGRESS",
      total_items: 4,
      pending_items: 1,
      created_at: new Date().toISOString(),
      items: [
        {
          id: "ari-1",
          user_id: "u-1",
          email: "alice.security@enterprise.com",
          role_name: "admin",
          permissions: ["compliance.*", "sre.*"],
          last_activity_at: new Date().toISOString(),
          review_status: "CONFIRMED",
          flagged_inactive: false,
        },
        {
          id: "ari-2",
          user_id: "u-2",
          email: "bob.contractor@external.com",
          role_name: "analyst",
          permissions: ["query.execute"],
          last_activity_at: new Date(Date.now() - 86400000 * 95).toISOString(),
          review_status: "REVOKE_RECOMMENDED",
          flagged_inactive: true,
        },
      ],
    },
  ];
}

export default function AccessReviewsPage() {
  const [reviews, setReviews] = useState<AccessReview[]>([]);
  const [launching, setLaunching] = useState<boolean>(false);

  useEffect(() => {
    async function loadReviews() {
      try {
        const res = await fetch("/api/v1/compliance/access-reviews");
        if (res.ok) {
          const data = await res.json();
          setReviews(data);
        } else {
          setReviews(getMockReviews());
        }
      } catch {
        setReviews(getMockReviews());
      }
    }
    loadReviews();
  }, []);

  async function launchCampaign() {
    setLaunching(true);
    try {
      await fetch("/api/v1/compliance/access-reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: `Quarterly Access Review Campaign - ${new Date().toLocaleDateString()}` }),
      });
      const res = await fetch("/api/v1/compliance/access-reviews");
      if (res.ok) {
        setReviews(await res.json());
      }
    } catch {
      // Re-load
    } finally {
      setLaunching(false);
    }
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Users className="h-5 w-5 text-primary" />
            Access Governance & Inactive Account Reviews
          </h1>
          <p className="text-xs text-muted-foreground">
            Regular audit reviews across privileged roles, inactive users (&gt;90 days), and stale permissions.
          </p>
        </div>
        <button
          onClick={launchCampaign}
          disabled={launching}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition"
        >
          <Play className={`h-3.5 w-3.5 ${launching ? "animate-spin" : ""}`} />
          {launching ? "Initiating..." : "Initiate Review Campaign"}
        </button>
      </div>

      <SecurityNav />

      {/* Reviews Campaigns */}
      <div className="space-y-4">
        {reviews.map((rev) => (
          <div key={rev.id} className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-border pb-2">
              <div>
                <h3 className="text-sm font-bold text-foreground">{rev.title}</h3>
                <p className="text-xs text-muted-foreground">
                  Initiated by {rev.initiated_by} on {new Date(rev.created_at).toLocaleDateString()}
                </p>
              </div>
              <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">
                {rev.status} ({rev.pending_items} pending / {rev.total_items} total)
              </span>
            </div>

            {/* Campaign items table */}
            {rev.items && rev.items.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/40 text-muted-foreground">
                    <tr>
                      <th className="p-2">User Email</th>
                      <th className="p-2">Role</th>
                      <th className="p-2">Last Activity</th>
                      <th className="p-2">Inactive Flag</th>
                      <th className="p-2 text-right">Review Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {rev.items.map((item) => (
                      <tr key={item.id} className="hover:bg-muted/20">
                        <td className="p-2 font-medium text-foreground">{item.email}</td>
                        <td className="p-2 font-mono text-[11px] text-muted-foreground">{item.role_name}</td>
                        <td className="p-2 text-muted-foreground text-[11px]">
                          {item.last_activity_at
                            ? new Date(item.last_activity_at).toLocaleDateString()
                            : "Never"}
                        </td>
                        <td className="p-2">
                          {item.flagged_inactive ? (
                            <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 px-2 py-0.5 text-[10px] font-bold text-rose-600 border border-rose-500/20">
                              <AlertTriangle className="h-3 w-3" /> &gt;90d Inactive
                            </span>
                          ) : (
                            <span className="text-emerald-500 text-[11px] font-medium">Active</span>
                          )}
                        </td>
                        <td className="p-2 text-right">
                          <span className="font-semibold text-[11px] text-foreground">
                            {item.review_status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
