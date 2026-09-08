"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import {
  Coins,
  Receipt,
  Wallet,
  Cpu,
  Cloud,
  AlertTriangle,
  TrendingUp,
  Sparkles,
  Scale,
} from "lucide-react";

export function FinOpsNav() {
  const pathname = usePathname();
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  const links = [
    { name: isTr ? "Genel Bakış" : "Overview", href: "/finops", icon: Coins },
    { name: isTr ? "Kullanım Gezgini" : "Usage Explorer", href: "/finops/usage", icon: Receipt },
    { name: isTr ? "Bütçeler & Kotalar" : "Budgets & Quotas", href: "/finops/budgets", icon: Wallet },
    { name: isTr ? "Modeller" : "Models", href: "/finops/models", icon: Cpu },
    { name: isTr ? "Sağlayıcılar" : "Providers", href: "/finops/providers", icon: Cloud },
    { name: isTr ? "Anomaliler" : "Anomalies", href: "/finops/anomalies", icon: AlertTriangle },
    { name: isTr ? "Tahminler" : "Forecasts", href: "/finops/forecasts", icon: TrendingUp },
    { name: isTr ? "Öneriler" : "Recommendations", href: "/finops/recommendations", icon: Sparkles },
    { name: isTr ? "Mutabakat" : "Reconciliation", href: "/finops/reconciliation", icon: Scale },
  ];

  return (
    <nav className="flex items-center gap-1 border-b border-border bg-card/40 p-1 rounded-lg backdrop-blur-sm overflow-x-auto">
      {links.map((link) => {
        const Icon = link.icon;
        const isActive = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${
              isActive
                ? "bg-primary text-primary-foreground shadow-sm"
                : "text-muted-foreground hover:bg-accent hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            <span>{link.name}</span>
          </Link>
        );
      })}
    </nav>
  );
}
