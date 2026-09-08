"use client";

import React, { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import { useAuth } from "@/features/auth/auth-context";
import { TenantSwitcher } from "./tenant-switcher";
import {
  Menu,
  ChevronRight,
  Search,
  Bell,
  Check,
  AlertTriangle,
  Info,
  LogOut,
  User as UserIcon,
  Shield,
} from "lucide-react";

interface TopbarProps {
  onOpenMobileMenu?: () => void;
  onOpenCommandPalette: () => void;
}

export function Topbar({
  onOpenMobileMenu,
  onOpenCommandPalette,
}: TopbarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { lang, setLang, t } = useLanguage();
  const { user, logout } = useAuth();

  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);

  // Dynamic route title
  const isTr = lang === "tr";

  const getPageTitle = (path: string) => {
    if (path === "/") return isTr ? "Genel Bakış" : (t.nav?.overview || "Overview");
    if (path.startsWith("/showcase")) return isTr ? "Platform & Mimari Turu" : "Platform & Architecture Tour";
    if (path.startsWith("/analyst")) return isTr ? "AI Analist Çalışma Alanı" : (t.nav?.aiAnalyst || "AI Analyst");
    if (path.startsWith("/executions")) return isTr ? "Çalıştırmalar & Zaman Çizelgesi" : "Executions & Timeline";
    if (path.startsWith("/datasets")) return isTr ? "Veri Setleri" : (t.nav?.datasets || "Datasets");
    if (path.startsWith("/semantic")) return isTr ? "Semantik Katman" : "Semantic Layer";
    if (path.startsWith("/approvals")) return isTr ? "Onaylar & Risk Çoğunluğu" : "Approvals & Risk Quorum";
    if (path.startsWith("/evaluation")) return isTr ? "Sürekli Değerlendirme" : (t.nav?.evaluation || "Continuous Evaluation");
    if (path.startsWith("/operations/reliability")) return isTr ? "Güvenilirlik & Kaos Senaryoları" : "Reliability & Chaos Scenarios";
    if (path.startsWith("/operations")) return isTr ? "Operasyonlar & SLO'lar" : "Operations & SLOs";
    if (path.startsWith("/security")) return isTr ? "Güvenlik & GRC" : "Security & GRC";
    if (path.startsWith("/finops")) return isTr ? "FinOps & Maliyet Yönetimi" : "FinOps & Cost Governance";
    if (path.startsWith("/settings")) return isTr ? "Ayarlar" : (t.nav?.settings || "Settings");
    return isTr ? "Kurumsal Platform" : "Enterprise Platform";
  };

  const NOTIFICATIONS = isTr
    ? [
        {
          id: "n1",
          text: "SLO uyumluluğu Q3 için %99.94 olarak korundu",
          time: "10 dk önce",
          type: "success" as const,
        },
        {
          id: "n2",
          text: "FinOps otomatik bütçe uyarısı: %74 tüketildi",
          time: "45 dk önce",
          type: "warn" as const,
        },
        {
          id: "n3",
          text: "12 veri seti için çok kiracılı sınıflandırma senkronizasyonu tamamlandı",
          time: "2 saat önce",
          type: "info" as const,
        },
      ]
    : [
        {
          id: "n1",
          text: "SLO compliance maintained at 99.94% for Q3",
          time: "10m ago",
          type: "success" as const,
        },
        {
          id: "n2",
          text: "FinOps automated budget alert: 74% consumed",
          time: "45m ago",
          type: "warn" as const,
        },
        {
          id: "n3",
          text: "Multi-tenant classification sync completed for 12 datasets",
          time: "2h ago",
          type: "info" as const,
        },
      ];

  const getInitials = (name?: string) => {
    if (!name) return "AH";
    const parts = name.trim().split(" ");
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
  };

  return (
    <header
      style={{
        height: 56,
        backgroundColor: "#0d0d0f",
        borderBottom: "1px solid #1a1a1d",
      }}
      className="sticky top-0 z-30 flex items-center px-4 gap-3 select-none"
    >
      {/* Mobile Menu Button */}
      {onOpenMobileMenu && (
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden text-[#a1a1aa] hover:text-[#fafafa] p-1.5 rounded-lg hover:bg-[#18181b] transition-colors cursor-pointer"
          aria-label="Open menu"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}

      {/* Breadcrumb Trail */}
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-xs text-[#52525b] hidden sm:inline">Enterprise AI</span>
        <ChevronRight className="h-3.5 w-3.5 text-[#3f3f46] shrink-0 hidden sm:inline" />
        <span className="text-[13.5px] font-semibold text-[#fafafa] tracking-tight truncate">
          {getPageTitle(pathname)}
        </span>
      </div>

      <div className="flex-1" />

      {/* Tenant Switcher */}
      <div className="hidden lg:block">
        <TenantSwitcher />
      </div>

      {/* ⌘K Search Bar */}
      <button
        onClick={onOpenCommandPalette}
        className="topbar-search items-center gap-2 rounded-lg border border-[#27272a] bg-[#18181b] px-3 py-1.5 text-xs text-[#71717a] hover:border-[#3f3f46] hover:text-[#a1a1aa] transition-colors cursor-pointer"
        title={isTr ? "Komut Paletini Aç (⌘K)" : "Open Command Palette (⌘K)"}
      >
        <Search className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">
          {isTr ? "Çalışma alanında ara..." : "Search workspace..."}
        </span>
        <span className="rounded bg-[#27272a] px-1.5 py-0.5 text-[10px] font-mono text-[#71717a]">
          ⌘K
        </span>
      </button>

      {/* Language Switcher */}
      <button
        onClick={() => setLang(lang === "en" ? "tr" : "en")}
        title={lang === "en" ? "Türkçeye geç" : "Switch to English"}
        className="flex items-center gap-1.5 rounded-md border border-[#27272a] bg-[#18181b] px-2.5 py-1 text-xs font-semibold text-[#a1a1aa] hover:border-[#6366f1] hover:text-[#818cf8] transition-colors cursor-pointer"
      >
        <span>{lang === "en" ? "🇹🇷" : "🇬🇧"}</span>
        <span>{lang === "en" ? "TR" : "EN"}</span>
      </button>

      {/* Notifications Drawer */}
      <div className="relative">
        <button
          onClick={() => {
            setShowNotifications((v) => !v);
            setShowUserMenu(false);
          }}
          aria-label={isTr ? "Bildirimler" : "Notifications"}
          className="relative flex h-8 w-8 items-center justify-center rounded-lg text-[#a1a1aa] hover:bg-[#18181b] hover:text-[#fafafa] transition-colors cursor-pointer"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-[#6366f1] border-2 border-[#0d0d0f] animate-pulse-dot" />
        </button>

        {showNotifications && (
          <div className="absolute right-0 top-10 w-80 rounded-xl border border-[#27272a] bg-[#18181b] shadow-2xl z-50 overflow-hidden animate-slide-up">
            <div className="flex items-center justify-between border-b border-[#27272a] px-4 py-2.5 text-xs font-semibold text-[#a1a1aa]">
              <span>{isTr ? "Bildirimler" : "Notifications"}</span>
              <span className="text-[11px] text-[#6366f1]">
                {isTr ? "Sistem Uyarıları" : "System Alerts"}
              </span>
            </div>
            <div className="divide-y divide-[#1f1f22] max-h-72 overflow-y-auto">
              {NOTIFICATIONS.map((n) => (
                <div key={n.id} className="flex items-start gap-3 p-3 hover:bg-[#1f1f22]/50 transition-colors">
                  <div
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-xs ${
                      n.type === "success"
                        ? "bg-[#22c55e]/15 text-[#22c55e]"
                        : n.type === "warn"
                        ? "bg-[#f59e0b]/15 text-[#f59e0b]"
                        : "bg-[#6366f1]/15 text-[#818cf8]"
                    }`}
                  >
                    {n.type === "success" ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : n.type === "warn" ? (
                      <AlertTriangle className="h-3.5 w-3.5" />
                    ) : (
                      <Info className="h-3.5 w-3.5" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-[#fafafa] leading-snug">{n.text}</div>
                    <div className="text-[10px] text-[#52525b] mt-1">{n.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* User Menu Avatar */}
      <div className="relative">
        <button
          onClick={() => {
            setShowUserMenu((v) => !v);
            setShowNotifications(false);
          }}
          className="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold text-white shadow-sm cursor-pointer"
          style={{
            background: "linear-gradient(135deg, #6366f1, #22d3ee)",
          }}
        >
          {getInitials(user?.full_name)}
        </button>

        {showUserMenu && (
          <div className="absolute right-0 top-10 w-52 rounded-xl border border-[#27272a] bg-[#18181b] shadow-2xl z-50 overflow-hidden animate-slide-up">
            <div className="border-b border-[#27272a] px-4 py-3">
              <div className="text-xs font-semibold text-[#fafafa] truncate">
                {user?.full_name || (isTr ? "Analist" : "Analyst")}
              </div>
              <div className="text-[11px] text-[#52525b] truncate">
                {user?.email || "analyst@enterprise.ai"}
              </div>
            </div>
            <div className="py-1">
              <button
                onClick={() => {
                  router.push("/settings");
                  setShowUserMenu(false);
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-xs text-[#a1a1aa] hover:bg-[#27272a] hover:text-[#fafafa] transition-colors cursor-pointer"
              >
                <UserIcon className="h-3.5 w-3.5" />
                <span>{isTr ? "Profil & Ayarlar" : "Profile & Settings"}</span>
              </button>
              <button
                onClick={() => {
                  router.push("/security");
                  setShowUserMenu(false);
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-xs text-[#a1a1aa] hover:bg-[#27272a] hover:text-[#fafafa] transition-colors cursor-pointer"
              >
                <Shield className="h-3.5 w-3.5" />
                <span>{isTr ? "Güvenlik & Roller" : "Security & Roles"}</span>
              </button>
              <button
                onClick={() => {
                  logout();
                  setShowUserMenu(false);
                }}
                className="flex w-full items-center gap-2 px-4 py-2 text-xs text-[#ef4444] hover:bg-[#ef4444]/10 transition-colors cursor-pointer"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span>{isTr ? "Çıkış Yap" : "Sign out"}</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
