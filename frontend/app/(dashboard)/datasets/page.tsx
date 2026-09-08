"use client";

import React from "react";
import { DatasetList } from "@/features/datasets/dataset-list";
import { useDatasets } from "@/hooks/use-platform";
import { useLanguage } from "@/contexts/language-context";
import { Database } from "lucide-react";

const SAMPLE_DATASETS = [
  {
    id: "ds-001",
    name: "financial_general_ledgers",
    source_type: "POSTGRESQL",
    status: "SYNCED",
    row_count: 1420500,
    column_count: 24,
    quality_score: 0.99,
    updated_at: "2026-09-07T18:00:00.000Z",
  },
  {
    id: "ds-002",
    name: "enterprise_customer_subscriptions",
    source_type: "POSTGRESQL",
    status: "SYNCED",
    row_count: 85200,
    column_count: 18,
    quality_score: 0.97,
    updated_at: "2026-09-07T17:00:00.000Z",
  },
  {
    id: "ds-003",
    name: "sec_10k_quarterly_filings_vector",
    source_type: "QDRANT_VECTOR",
    status: "INDEXED",
    row_count: 42000,
    column_count: 1536,
    quality_score: 0.96,
    updated_at: "2026-09-06T18:00:00.000Z",
  },
];

export default function DatasetsPage() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const { data } = useDatasets();
  const sampleDatasets = data && data.length > 0 ? data : SAMPLE_DATASETS;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500/10 text-sky-500">
          <Database className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            {isTr ? "Kurumsal Veri Setleri & Soykütüğü Kataloğu" : "Enterprise Datasets & Lineage Catalog"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "İçeri aktarılmış ilişkisel tablolar, vektörleştirilmiş belgeler ve senkronize operasyonel veri depoları."
              : "Ingested relational tables, vectorized documents, and synchronized operational data stores."}
          </p>
        </div>
      </div>

      <DatasetList datasets={sampleDatasets} />
    </div>
  );
}
