"use client";

import React, { useState } from "react";
import Link from "next/link";
import { DatasetItem } from "@/types/platform";
import { useLanguage } from "@/contexts/language-context";
import { Database, Search, CheckCircle2, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { formatDate, formatPercent } from "@/lib/utils";

interface DatasetListProps {
  datasets: DatasetItem[];
}

export function DatasetList({ datasets }: DatasetListProps) {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [search, setSearch] = useState("");

  const filtered = datasets.filter((d) =>
    d.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Search Header */}
      <div className="flex items-center justify-between gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={isTr ? "Veri setlerinde ara..." : "Search datasets..."}
            className="h-8 pl-8 text-xs bg-card"
          />
        </div>
        <span className="text-xs text-muted-foreground">
          {filtered.length} {isTr ? "kurumsal veri seti" : "enterprise datasets"}
        </span>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((item) => (
          <div
            key={item.id}
            className="rounded-xl border border-border bg-card p-4 shadow-xs space-y-3 hover:border-border/80 transition-all flex flex-col justify-between"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-500/10 text-sky-500">
                    <Database className="h-4 w-4" />
                  </div>
                  <h4 className="text-xs font-bold text-foreground truncate max-w-[160px]">
                    {item.name}
                  </h4>
                </div>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  <CheckCircle2 className="h-3 w-3" />
                  {item.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground pt-1">
                <div>{isTr ? "Kaynak:" : "Source:"} <span className="text-foreground font-mono">{item.source_type}</span></div>
                <div>{isTr ? "Satır:" : "Rows:"} <span className="text-foreground font-mono">{item.row_count?.toLocaleString() || "—"}</span></div>
                <div>{isTr ? "Sütun:" : "Columns:"} <span className="text-foreground font-mono">{item.column_count || "—"}</span></div>
                <div>{isTr ? "Kalite:" : "Quality:"} <span className="text-emerald-600 font-mono font-bold">{formatPercent(item.quality_score ?? 0.98)}</span></div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-border/60 text-[10px] text-muted-foreground">
              <span>{isTr ? "Güncellendi:" : "Updated:"} {formatDate(item.updated_at)}</span>
              <Link href={`/datasets/${item.id}`}>
                <Button variant="ghost" size="sm" className="h-6 gap-1 text-[11px] text-primary p-0">
                  <span>{isTr ? "İncele" : "Explore"}</span>
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
