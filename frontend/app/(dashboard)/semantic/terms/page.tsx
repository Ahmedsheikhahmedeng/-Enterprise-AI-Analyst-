"use client";

import React from "react";
import Link from "next/link";
import { TermList } from "@/features/semantic/term-list";
import { useSemanticTerms } from "@/hooks/use-platform";
import { ArrowLeft, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function TermsPage() {
  const { data } = useSemanticTerms();

  const sampleTerms = data && data.length > 0 ? data : [
    {
      id: "term-001",
      name: "Annual Recurring Revenue (ARR)",
      definition: "The annualized value of customer subscription contract commitments excluding one-off setup or professional fees.",
      status: "PUBLISHED" as const,
      category: "FINANCIAL",
      created_at: new Date().toISOString(),
    },
    {
      id: "term-002",
      name: "Net Revenue Retention (NRR)",
      definition: "Percentage of recurring revenue retained from existing customers over a 12-month period, including expansions and churn.",
      status: "PUBLISHED" as const,
      category: "FINANCIAL",
      created_at: new Date().toISOString(),
    },
    {
      id: "term-003",
      name: "Monthly Active Account (MAA)",
      definition: "An organization account that performed at least one verified API query or dashboard analysis within the past 30 days.",
      status: "REVIEW" as const,
      category: "OPERATIONAL",
      created_at: new Date().toISOString(),
    },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/semantic">
          <Button variant="outline" size="sm" className="h-8 gap-1 text-xs">
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Semantic Layer</span>
          </Button>
        </Link>
      </div>

      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <BookOpen className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            Business Glossary Terms
          </h1>
          <p className="text-xs text-muted-foreground">
            Canonical semantic terminology mapped to enterprise database columns.
          </p>
        </div>
      </div>

      <TermList terms={sampleTerms} />
    </div>
  );
}
