"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useAuth } from "@/features/auth/auth-context";
import {
  Sparkles,
  Bot,
  LayoutDashboard,
  Database,
  History,
  ShieldCheck,
  Coins,
  Activity,
  Target,
  Settings,
  ShieldAlert,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
  Layers,
} from "lucide-react";

interface SidebarProps {
  className?: string;
  isMobile?: boolean;
  onItemClick?: () => void;
}

interface NavItem {
  id: string;
  labelKey: string;
  fallback: string;
  turkish: string;
  href: string;
  icon: LucideIcon;
  group: "workspace" | "governance" | "operations" | "security" | "finops" | "admin";
  badge?: string;
}

export function Sidebar({ className = "", isMobile = false, onItemClick }: SidebarProps) {
  const pathname = usePathname();
  const { lang, t } = useLanguage();
  const { user, canApprove, canViewEvaluation } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const isCollapsed = isMobile ? false : collapsed;
  const isTr = lang === "tr";

  const GROUPS = [
    { id: "workspace", label: isTr ? "Çalışma Alanı" : (t.nav?.workspace || "Workspace") },
    { id: "governance", label: isTr ? "Yönetişim & Denetim" : "Governance" },
    { id: "operations", label: isTr ? "Operasyon & SRE" : "Operations & SRE" },
    { id: "security", label: isTr ? "Güvenlik & Uyum" : "Security & Trust" },
    { id: "finops", label: isTr ? "FinOps Merkezi" : "FinOps Hub" },
    { id: "admin", label: isTr ? "Yönetim" : (t.nav?.admin || "Admin") },
  ];

  const NAV: NavItem[] = [
    {
      id: "overview",
      labelKey: "overview",
      fallback: "Overview",
      turkish: "Genel Bakış",
      href: "/",
      icon: LayoutDashboard,
      group: "workspace",
    },
    {
      id: "showcase",
      labelKey: "showcase",
      fallback: "Platform Architecture",
      turkish: "Platform Mimarisi",
      href: "/showcase",
      icon: Sparkles,
      group: "workspace",
    },
    {
      id: "analyst",
      labelKey: "aiAnalyst",
      fallback: "AI Analyst",
      turkish: "AI Analist",
      href: "/analyst",
      icon: Bot,
      group: "workspace",
    },
    {
      id: "executions",
      labelKey: "conversations",
      fallback: "Executions",
      turkish: "Yürütmeler & Süreç",
      href: "/executions",
      icon: History,
      group: "workspace",
    },
    {
      id: "datasets",
      labelKey: "datasets",
      fallback: "Datasets",
      turkish: "Veri Setleri",
      href: "/datasets",
      icon: Database,
      group: "workspace",
    },
    {
      id: "semantic",
      labelKey: "dataSources",
      fallback: "Semantic Layer",
      turkish: "Semantik Katman",
      href: "/semantic",
      icon: Layers,
      group: "workspace",
    },
    {
      id: "approvals",
      labelKey: "approvals",
      fallback: "Approvals",
      turkish: "Onaylar & Risk",
      href: "/approvals",
      icon: ShieldAlert,
      group: "governance",
      badge: canApprove ? "Active" : undefined,
    },
    ...(canViewEvaluation
      ? [
          {
            id: "evaluation",
            labelKey: "evaluation",
            fallback: "Evaluation",
            turkish: "Değerlendirme",
            href: "/evaluation",
            icon: Target,
            group: "governance" as const,
          },
        ]
      : []),
    {
      id: "operations",
      labelKey: "analytics",
      fallback: "Operations",
      turkish: "Operasyonlar",
      href: "/operations",
      icon: Activity,
      group: "operations",
    },
    {
      id: "security",
      labelKey: "auditLogs",
      fallback: "Security & GRC",
      turkish: "Güvenlik & GRC",
      href: "/security",
      icon: ShieldCheck,
      group: "security",
    },
    {
      id: "finops",
      labelKey: "finops",
      fallback: "FinOps & Cost",
      turkish: "FinOps & Maliyet",
      href: "/finops",
      icon: Coins,
      group: "finops",
    },
    {
      id: "settings",
      labelKey: "settings",
      fallback: "Settings",
      turkish: "Ayarlar",
      href: "/settings",
      icon: Settings,
      group: "admin",
    },
  ];

  const getInitials = (name?: string) => {
    if (!name) return "EA";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <aside
      style={{
        width: isCollapsed ? 68 : 232,
        backgroundColor: "#0d0d0f",
        borderRight: "1px solid #1a1a1d",
      }}
      className={`flex flex-col min-h-screen shrink-0 transition-all duration-200 select-none ${className}`}
    >
      {/* Brand Header */}
      <div
        className={`flex h-14 items-center border-b border-[#1a1a1d] shrink-0 ${
          isCollapsed ? "justify-center px-2" : "justify-between px-4"
        }`}
      >
        <Link href="/" className="flex items-center gap-2.5 min-w-0" onClick={onItemClick}>
          <div
            className="flex h-7 w-7 items-center justify-center rounded-lg shadow-md shrink-0"
            style={{
              background: "linear-gradient(135deg, #6366f1 0%, #22d3ee 100%)",
              boxShadow: "0 4px 14px rgba(99,102,241,0.4)",
            }}
          >
            <Sparkles className="h-4 w-4 text-white stroke-[2.4]" />
          </div>
          {!isCollapsed && (
            <div className="flex flex-col leading-tight min-w-0">
              <span className="text-[13.5px] font-bold text-[#fafafa] tracking-tight truncate">
                Enterprise AI
              </span>
              <span className="text-[9.5px] font-semibold text-[#52525b] uppercase tracking-wider truncate">
                {isTr ? "Analist Platformu" : "Analyst Platform"}
              </span>
            </div>
          )}
        </Link>

        {!isMobile && !isCollapsed && (
          <button
            onClick={() => setCollapsed(true)}
            className="text-[#52525b] hover:text-[#fafafa] p-1 rounded hover:bg-[#18181b] transition-colors cursor-pointer"
            title={isTr ? "Menüyü Daralt" : "Collapse sidebar"}
            aria-label="Collapse sidebar"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Nav Groups */}
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-3">
        {isCollapsed && !isMobile && (
          <div className="flex justify-center pb-2">
            <button
              onClick={() => setCollapsed(false)}
              className="text-[#52525b] hover:text-[#fafafa] p-1.5 rounded-md hover:bg-[#18181b] transition-colors cursor-pointer"
              title={isTr ? "Menüyü Genişlet" : "Expand sidebar"}
              aria-label="Expand sidebar"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {GROUPS.map((group) => {
          const items = NAV.filter((n) => n.group === group.id);
          if (items.length === 0) return null;

          return (
            <div key={group.id} className="space-y-0.5">
              {!isCollapsed && (
                <div className="px-2.5 py-1 text-[10px] font-semibold tracking-wider text-[#3f3f46] uppercase">
                  {group.label}
                </div>
              )}
              {items.map((item) => {
                const Icon = item.icon;
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname === item.href || pathname?.startsWith(`${item.href}/`);

                const displayLabel = isTr ? item.turkish : item.fallback;

                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    onClick={onItemClick}
                    title={isCollapsed ? displayLabel : undefined}
                    className={`relative flex items-center gap-2.5 rounded-lg text-xs transition-colors group cursor-pointer ${
                      isCollapsed ? "justify-center p-2.5" : "px-2.5 py-2"
                    } ${
                      isActive
                        ? "text-[#a5b4fc] font-semibold"
                        : "text-[#71717a] hover:text-[#e4e4e7] hover:bg-white/[0.04]"
                    }`}
                    style={{
                      background: isActive
                        ? "linear-gradient(90deg, rgba(99,102,241,0.16), rgba(99,102,241,0.06))"
                        : "transparent",
                      boxShadow: isActive ? "inset 0 0 0 1px rgba(99,102,241,0.22)" : "none",
                    }}
                  >
                    {isActive && !isCollapsed && (
                      <span
                        className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 rounded-r"
                        style={{ background: "linear-gradient(180deg,#6366f1,#22d3ee)" }}
                      />
                    )}
                    <Icon
                      className={`h-4 w-4 shrink-0 transition-transform group-hover:scale-105 ${
                        isActive ? "text-[#818cf8]" : "text-[#71717a]"
                      }`}
                      strokeWidth={isActive ? 2.3 : 2}
                    />
                    {!isCollapsed && (
                      <span className="truncate flex-1">{displayLabel}</span>
                    )}
                    {!isCollapsed && item.badge && (
                      <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[9.5px] font-semibold text-amber-400">
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* User Footer */}
      <div
        className={`border-t border-[#1a1a1d] p-3 flex items-center shrink-0 ${
          isCollapsed ? "justify-center" : "gap-2.5"
        }`}
      >
        <div className="relative shrink-0">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold text-white"
            style={{
              background: "linear-gradient(135deg, #6366f1, #22d3ee)",
            }}
          >
            {getInitials(user?.full_name)}
          </div>
          <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-[#22c55e] border-2 border-[#0d0d0f]" />
        </div>
        {!isCollapsed && (
          <div className="flex flex-col min-w-0 flex-1 leading-tight">
            <span className="text-xs font-medium text-[#fafafa] truncate">
              {user?.full_name || (isTr ? "Kurumsal Kullanıcı" : "Enterprise User")}
            </span>
            <span className="text-[10px] text-[#52525b] truncate">
              {user?.role ? user.role.toUpperCase() : (isTr ? "ANALİST" : "ANALYST")} · Acme Corp
            </span>
          </div>
        )}
      </div>
    </aside>
  );
}
