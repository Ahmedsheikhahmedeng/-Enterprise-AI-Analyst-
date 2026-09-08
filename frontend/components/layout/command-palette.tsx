"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useLanguage } from "@/contexts/language-context";
import {
  Search,
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
  X,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

interface CommandItem {
  id: string;
  label: string;
  group: string;
  icon: LucideIcon;
  href: string;
  shortcut?: string;
}

export function CommandPalette({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const { lang, t } = useLanguage();
  const isTr = lang === "tr";
  const [query, setQuery] = useState("");

  const ITEMS: CommandItem[] = [
    { id: "showcase", label: isTr ? "Platform & Mimari Turu" : "Platform & Architecture Tour", group: isTr ? "Platform" : "Platform", icon: Sparkles, href: "/showcase", shortcut: "S" },
    { id: "overview", label: isTr ? "Genel Bakış" : (t.nav?.overview || "Overview"), group: isTr ? "Çalışma Alanı" : "Workspace", icon: LayoutDashboard, href: "/" },
    { id: "analyst", label: isTr ? "AI Analist" : (t.nav?.aiAnalyst || "AI Analyst"), group: isTr ? "Çalışma Alanı" : "Workspace", icon: Bot, href: "/analyst", shortcut: "A" },
    { id: "executions", label: isTr ? "Çalıştırmalar & Zaman Çizelgesi" : "Executions & Timeline", group: isTr ? "Çalışma Alanı" : "Workspace", icon: History, href: "/executions" },
    { id: "datasets", label: isTr ? "Veri Setleri" : (t.nav?.datasets || "Datasets"), group: isTr ? "Veri" : "Data", icon: Database, href: "/datasets" },
    { id: "approvals", label: isTr ? "Onaylar & Risk Çoğunluğu" : "Approvals & Risk Quorum", group: isTr ? "Yönetişim" : "Governance", icon: ShieldAlert, href: "/approvals" },
    { id: "evaluation", label: isTr ? "Sürekli Değerlendirme" : (t.nav?.evaluation || "Continuous Evaluation"), group: isTr ? "Yönetişim" : "Governance", icon: Target, href: "/evaluation" },
    { id: "operations", label: isTr ? "Operasyonlar & SLO'lar" : "Operations & SLOs", group: isTr ? "Operasyon" : "Operations", icon: Activity, href: "/operations" },
    { id: "reliability", label: isTr ? "Güvenilirlik & Senaryolar" : "Reliability & Scenarios", group: isTr ? "Operasyon" : "Operations", icon: Activity, href: "/operations/reliability" },
    { id: "security", label: isTr ? "Güvenlik & GRC" : "Security & GRC", group: isTr ? "Güvenlik" : "Security", icon: ShieldCheck, href: "/security" },
    { id: "finops", label: isTr ? "FinOps & Maliyet Yönetimi" : "FinOps & Cost Governance", group: isTr ? "FinOps" : "FinOps", icon: Coins, href: "/finops" },
    { id: "settings", label: isTr ? "Ayarlar" : (t.nav?.settings || "Settings"), group: isTr ? "Yönetim" : "Admin", icon: Settings, href: "/settings" },
  ];

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onClose();
      }
      if (e.key === "Escape" && open) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const filtered = query.trim()
    ? ITEMS.filter((item) =>
        item.label.toLowerCase().includes(query.toLowerCase()) ||
        item.group.toLowerCase().includes(query.toLowerCase())
      )
    : ITEMS;

  const handleSelect = (href: string) => {
    router.push(href);
    onClose();
    setQuery("");
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 bg-black/70 backdrop-blur-sm animate-fade-in"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-lg rounded-xl border border-[#27272a] bg-[#111113] shadow-2xl overflow-hidden animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 border-b border-[#1f1f22] px-4 py-3">
          <Search className="h-4 w-4 text-[#71717a] shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              isTr
                ? "Komut, çalışma alanı veya veri seti ara... (⌘K)"
                : "Search commands, workspaces, or datasets... (⌘K)"
            }
            autoFocus
            className="flex-1 bg-transparent text-sm text-[#fafafa] placeholder-[#52525b] outline-none"
          />
          {query && (
            <button
              onClick={() => setQuery("")}
              className="text-[#71717a] hover:text-[#fafafa] p-0.5"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <span className="rounded border border-[#27272a] bg-[#18181b] px-1.5 py-0.5 text-[10px] font-mono text-[#71717a]">
            ESC
          </span>
        </div>

        {/* Results list */}
        <div className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="py-8 text-center text-xs text-[#71717a]">
              {isTr ? "Eşleşen komut veya sayfa bulunamadı." : "No matching commands or pages found."}
            </div>
          ) : (
            <div className="space-y-1">
              {filtered.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => handleSelect(item.href)}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-xs text-[#a1a1aa] hover:bg-[#18181b] hover:text-[#fafafa] transition-colors group cursor-pointer"
                  >
                    <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[#1f1f22] text-[#71717a] group-hover:text-[#a5b4fc] group-hover:bg-[#6366f1]/10 shrink-0">
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-[#e4e4e7] truncate">
                        {item.label}
                      </div>
                      <div className="text-[10px] text-[#52525b]">
                        {item.group}
                      </div>
                    </div>
                    {item.shortcut && (
                      <span className="font-mono text-[10px] text-[#52525b] border border-[#27272a] rounded px-1">
                        {item.shortcut}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between border-t border-[#1f1f22] px-4 py-2 text-[11px] text-[#52525b] bg-[#0d0d0f]">
          <span>{isTr ? "Herhangi bir yerde açmak için ⌘K kullanın" : "Use ⌘K to toggle anywhere"}</span>
          <span className="font-mono">Enterprise AI Analyst v2.4</span>
        </div>
      </div>
    </div>
  );
}
