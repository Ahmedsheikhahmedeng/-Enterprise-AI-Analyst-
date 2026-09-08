"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import {
  ShieldCheck,
  CheckCircle2,
  AlertOctagon,
  FileCheck,
  Users,
  EyeOff,
  Database,
} from "lucide-react";

export function SecurityNav() {
  const pathname = usePathname();
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  const links = [
    { name: isTr ? "Genel Bakış" : "Overview", href: "/security", icon: ShieldCheck },
    { name: isTr ? "Kontroller" : "Controls", href: "/security/controls", icon: CheckCircle2 },
    { name: isTr ? "Bulgular" : "Findings", href: "/security/findings", icon: AlertOctagon },
    { name: isTr ? "Denetim Kanıtları" : "Audit Evidence", href: "/security/evidence", icon: FileCheck },
    { name: isTr ? "Erişim İncelemeleri" : "Access Reviews", href: "/security/access-reviews", icon: Users },
    { name: isTr ? "Gizlilik & Askılar" : "Privacy & Holds", href: "/security/privacy", icon: EyeOff },
    { name: isTr ? "Veri Sınıflandırma" : "Data Classification", href: "/security/data", icon: Database },
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
