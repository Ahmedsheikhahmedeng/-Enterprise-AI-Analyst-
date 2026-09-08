"use client";

import React, { useState } from "react";
import { SemanticTerm } from "@/types/platform";
import { useAuth } from "@/features/auth/auth-context";
import { BookOpen, Search, ShieldCheck } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface TermListProps {
  terms: SemanticTerm[];
}

export function TermList({ terms }: TermListProps) {
  const { canPublish } = useAuth();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const filtered = terms.filter((term) => {
    const matchSearch =
      term.name.toLowerCase().includes(search.toLowerCase()) ||
      term.definition.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "ALL" || term.status === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <div className="space-y-4">
      {/* Search & Filter */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search business glossary..."
              className="h-8 pl-8 text-xs bg-card"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter terms by governance status"
            className="h-8 rounded-lg border border-border bg-card px-2.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="ALL">All Statuses</option>
            <option value="PUBLISHED">Published</option>
            <option value="APPROVED">Approved</option>
            <option value="REVIEW">In Review</option>
            <option value="DRAFT">Draft</option>
          </select>
        </div>

        <span className="text-xs text-muted-foreground">
          {filtered.length} glossary terms
        </span>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="rounded-xl border border-border bg-card p-4 space-y-2 shadow-xs"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                <h4 className="text-xs font-bold text-foreground">{item.name}</h4>
              </div>
              <span className="rounded bg-primary/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-primary">
                {item.status}
              </span>
            </div>

            <p className="text-xs text-muted-foreground leading-relaxed">
              {item.definition}
            </p>

            {item.category && (
              <div className="pt-2 text-[10px] text-muted-foreground">
                Domain: <span className="font-semibold text-foreground">{item.category}</span>
              </div>
            )}

            {canPublish && item.status === "REVIEW" && (
              <div className="pt-2 border-t border-border flex justify-end">
                <Button size="sm" variant="outline" className="h-6 text-[11px] gap-1 text-emerald-600">
                  <ShieldCheck className="h-3 w-3" />
                  <span>Verify & Publish</span>
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
