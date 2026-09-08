"use client";

import React from "react";
import Link from "next/link";
import { Layers, BookOpen, Calculator, Share2, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/language-context";

export default function SemanticPage() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  const sections = [
    {
      title: isTr ? "İş Terimleri Sözlüğü" : "Business Glossary & Terms",
      description: isTr
        ? "Semantik kaymayı önlemek için kurumsal kavramlar için standartlaştırılmış tanımlar."
        : "Standardized canonical definitions for enterprise concepts to prevent semantic drift.",
      href: "/semantic/terms",
      icon: BookOpen,
      count: isTr ? "48 Terim" : "48 Terms",
    },
    {
      title: isTr ? "Hesaplanan Metrikler & Formüller" : "Calculated Metrics & Formulas",
      description: isTr
        ? "Tablolarla eşleştirilmiş doğrulanmış SQL hesaplama formülleri (ör. ARR, Brüt Kâr Marjı, Net Kayıp Oranı)."
        : "Verified SQL calculation formulas (e.g. ARR, Gross Margin, Net Churn) mapped to tables.",
      href: "/semantic/metrics",
      icon: Calculator,
      count: isTr ? "24 Metrik" : "24 Metrics",
    },
    {
      title: isTr ? "Bilgi Grafı İlişkileri" : "Knowledge Graph Relationships",
      description: isTr
        ? "Kurumsal veri modelleri genelinde varlıklar arası bağlantılar ve çok atlamalı semantik grafik yolları."
        : "Inter-entity links and multi-hop semantic graph pathways across enterprise data models.",
      href: "/semantic/graph",
      icon: Share2,
      count: isTr ? "128 Düğüm" : "128 Nodes",
    },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/10 text-amber-500">
          <Layers className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            {isTr ? "Semantik Katman & Kurumsal Bilgi Grafı" : "Semantic Layer & Enterprise Knowledge Graph"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "Birleşik iş taksonomisi, doğrulanmış hesaplama formülleri ve varlık ilişkileri grafı."
              : "Unified business taxonomy, verified calculation formulas, and relationship graphs."}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {sections.map((sec) => {
          const Icon = sec.icon;
          return (
            <div
              key={sec.title}
              className="rounded-xl border border-border bg-card p-5 space-y-4 shadow-xs flex flex-col justify-between hover:border-border/80 transition-all"
            >
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-4 w-4" />
                  </div>
                  <span className="text-[11px] font-mono text-muted-foreground">
                    {sec.count}
                  </span>
                </div>
                <h3 className="text-sm font-bold text-foreground">{sec.title}</h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {sec.description}
                </p>
              </div>

              <div className="pt-2 border-t border-border/50">
                <Link href={sec.href}>
                  <Button variant="outline" size="sm" className="w-full justify-between text-xs h-8">
                    <span>{isTr ? "Bölümü İncele" : "Explore Section"}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                </Link>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
