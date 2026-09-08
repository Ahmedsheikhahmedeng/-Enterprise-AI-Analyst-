"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useLanguage } from "@/contexts/language-context";
import { useAuth } from "@/features/auth/auth-context";
import {
  Bot,
  Sparkles,
  Database,
  Coins,
  Activity,
  ArrowUpRight,
  FileText,
  FileSpreadsheet,
  Upload,
  type LucideIcon,
} from "lucide-react";

interface KpiCard {
  label: string;
  value: string;
  change: string;
  up: boolean;
  sub: string;
  color: string;
  icon: LucideIcon;
}

interface RecentAnalysis {
  id: string;
  title: string;
  status: "completed" | "running" | "failed";
  time: string;
  sources: number;
}

interface RecentDoc {
  id: string;
  name: string;
  size: string;
  status: "ready" | "processing" | "failed";
  pages?: number | null;
}

const SPEND_TREND_DATA = [
  { month: "Apr", spend: 3240, budget: 5000 },
  { month: "May", spend: 3890, budget: 5000 },
  { month: "Jun", spend: 4120, budget: 5000 },
  { month: "Jul", spend: 4680, budget: 5500 },
  { month: "Aug", spend: 4310, budget: 5500 },
  { month: "Sep", spend: 4790, budget: 6000 },
];

const QUERY_VOLUME_DATA = [
  { day: "Mon", queries: 284 },
  { day: "Tue", queries: 371 },
  { day: "Wed", queries: 319 },
  { day: "Thu", queries: 452 },
  { day: "Fri", queries: 398 },
  { day: "Sat", queries: 124 },
  { day: "Sun", queries: 89 },
];

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  ready: "#22c55e",
  running: "#f59e0b",
  processing: "#f59e0b",
  failed: "#ef4444",
};

interface TooltipPayloadItem {
  name: string;
  value: number | string;
  color?: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#18181b",
        border: "1px solid #27272a",
        borderRadius: 6,
        padding: "8px 12px",
        fontSize: 12,
      }}
    >
      <div style={{ color: "#71717a", marginBottom: 4 }}>{label}</div>
      {payload.map((p) => (
        <div key={p.name} style={{ color: p.color, fontFamily: "var(--font-mono)" }}>
          {p.name}: {p.value}
        </div>
      ))}
    </div>
  );
};

export default function OverviewDashboardPage() {
  const router = useRouter();
  const { lang, t } = useLanguage();
  const isTr = lang === "tr";
  const { user } = useAuth();

  const [systemOnline, setSystemOnline] = useState(true);

  const hour = new Date().getHours();
  const greeting =
    hour < 12
      ? isTr ? "Günaydın" : (t.dashboard?.greetMorning || "Good morning")
      : hour < 17
      ? isTr ? "Tünaydın" : (t.dashboard?.greetAfternoon || "Good afternoon")
      : isTr ? "İyi akşamlar" : (t.dashboard?.greetEvening || "Good evening");

  // Fetch live system health
  useEffect(() => {
    async function fetchHealth() {
      try {
        const res = await fetch("http://localhost:8000/api/v1/product/health");
        if (res.ok) {
          const data = await res.json();
          setSystemOnline(data.status === "healthy" || data.status === "ok");
        }
      } catch {
        // local dev nominal fallback
      }
    }
    fetchHealth();
  }, []);

  const KPIS: KpiCard[] = [
    {
      label: isTr ? "Aylık FinOps Harcaması" : "Monthly FinOps Spend",
      value: "$4,790",
      change: "-4.2%",
      up: false,
      sub: isTr ? "kota dahilinde" : "within quota",
      color: "#22d3ee",
      icon: Coins,
    },
    {
      label: isTr ? "İndekslenen Bilgi" : "Indexed Knowledge",
      value: "84,210",
      change: "+12.4%",
      up: true,
      sub: isTr ? "kayıt indekslendi" : "records indexed",
      color: "#6366f1",
      icon: Database,
    },
    {
      label: isTr ? "AI Analist Sorguları" : "AI Analyst Inquiries",
      value: "1,842",
      change: "+22%",
      up: true,
      sub: isTr ? "bu ay" : "this month",
      color: "#22c55e",
      icon: Sparkles,
    },
    {
      label: isTr ? "Platform SLO Durumu" : "Platform SLO",
      value: "99.95%",
      change: "+0.02%",
      up: true,
      sub: isTr ? "operasyonel" : "operational",
      color: "#f59e0b",
      icon: Activity,
    },
  ];

  const RECENT_ANALYSES: (RecentAnalysis & { titleTr: string; timeTr: string })[] = [
    {
      id: "1",
      title: "Q3 Enterprise Revenue & Margin Breakdown",
      titleTr: "Q3 Kurumsal Gelir & Kar Marjı Dağılımı",
      status: "completed",
      time: "2h ago",
      timeTr: "2 saat önce",
      sources: 8,
    },
    {
      id: "2",
      title: "Customer Churn Prediction by Segment",
      titleTr: "Segmente Göre Müşteri Kaybı Tahmini",
      status: "completed",
      time: "5h ago",
      timeTr: "5 saat önce",
      sources: 12,
    },
    {
      id: "3",
      title: "Regional Sales & Pipeline Discrepancies",
      titleTr: "Bölgesel Satış & Pipeline Uyuşmazlıkları",
      status: "running",
      time: "Running...",
      timeTr: "Çalışıyor...",
      sources: 4,
    },
    {
      id: "4",
      title: "Infrastructure Routing Cost Optimization",
      titleTr: "Altyapı Yönlendirme Maliyet Optimizasyonu",
      status: "completed",
      time: "Yesterday",
      timeTr: "Dün",
      sources: 6,
    },
  ];

  const RECENT_DOCS: RecentDoc[] = [
    {
      id: "d1",
      name: "Q3_Financial_Performance_Review.pdf",
      size: "2.4 MB",
      status: "ready",
      pages: 48,
    },
    {
      id: "d2",
      name: "Customer_Success_Quarterly_Ledger.xlsx",
      size: "890 KB",
      status: "ready",
      pages: 12,
    },
    {
      id: "d3",
      name: "Enterprise_Pipeline_Audit_2026.csv",
      size: "1.1 MB",
      status: "processing",
      pages: null,
    },
    {
      id: "d4",
      name: "Board_Security_Posture_Briefing.pdf",
      size: "4.7 MB",
      status: "ready",
      pages: 32,
    },
  ];

  return (
    <div className="page-pad mx-auto max-w-7xl space-y-6">
      {/* Header Greeting Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-2 border-b border-[#1f1f22]">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-[#fafafa]">
            {greeting}, {user?.full_name?.split(" ")[0] || (isTr ? "Analist" : "Analyst")}.
          </h1>
          <p className="text-xs text-[#71717a] mt-0.5">
            {isTr
              ? "Kurumsal Zeka Platformu · Kiracı: Acme Corp Production"
              : "Enterprise Intelligence Platform · Tenant: Acme Corp Production"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-full border border-[#27272a] bg-[#111113] px-3 py-1 text-xs text-[#a1a1aa]">
            <span
              className={`h-2 w-2 rounded-full ${
                systemOnline ? "bg-[#22c55e] animate-pulse-dot" : "bg-[#ef4444]"
              }`}
            />
            <span className="font-medium">
              {systemOnline
                ? isTr
                  ? "Tüm Alt Sistemler Normal"
                  : "All Subsystems Nominal"
                : isTr
                ? "Servis Kesintisi"
                : "Service Disruption"}
            </span>
          </div>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid-4">
        {KPIS.map((kpi) => {
          const Icon = kpi.icon;
          return (
            <div
              key={kpi.label}
              className="rounded-xl border border-[#1f1f22] bg-[#111113] p-4 flex flex-col justify-between transition-all hover:border-[#27272a]"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-[#71717a]">{kpi.label}</span>
                <div
                  className="flex h-7 w-7 items-center justify-center rounded-lg"
                  style={{
                    backgroundColor: `${kpi.color}15`,
                    color: kpi.color,
                  }}
                >
                  <Icon className="h-4 w-4" />
                </div>
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold tracking-tight text-[#fafafa] font-mono">
                  {kpi.value}
                </span>
                <span
                  className={`text-[11px] font-semibold font-mono ${
                    kpi.up ? "text-[#22c55e]" : "text-[#22d3ee]"
                  }`}
                >
                  {kpi.change}
                </span>
              </div>
              <div className="text-[11px] text-[#52525b] mt-1 capitalize">{kpi.sub}</div>
            </div>
          );
        })}
      </div>

      {/* Charts Split Row */}
      <div className="grid-rev-charts">
        {/* Spend & Quota AreaChart */}
        <div className="rounded-xl border border-[#1f1f22] bg-[#111113] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-[#fafafa]">
                {isTr ? "FinOps Harcaması vs Tahsis Edilen Kota" : "FinOps Spend vs Allocated Quota"}
              </div>
              <div className="text-xs text-[#71717a] mt-0.5">
                {isTr
                  ? "Aylık LLM çıkarım & altyapı defteri ($USD)"
                  : "Monthly LLM inference & infrastructure ledger ($USD)"}
              </div>
            </div>
            <Link
              href="/finops"
              className="text-xs font-medium text-[#818cf8] hover:text-[#a5b4fc] flex items-center gap-1"
            >
              {isTr ? "Merkez" : "Hub"} <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>

          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={SPEND_TREND_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="budgetGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#22d3ee" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#1f1f22" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: "#52525b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#52525b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="spend"
                name={isTr ? "Gerçekleşen Harcama" : "Actual Spend"}
                stroke="#6366f1"
                fill="url(#spendGrad)"
                strokeWidth={2}
                dot={false}
              />
              <Area
                type="monotone"
                dataKey="budget"
                name={isTr ? "Bütçe Kotası" : "Budget Quota"}
                stroke="#22d3ee"
                fill="url(#budgetGrad)"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Query Activity BarChart */}
        <div className="rounded-xl border border-[#1f1f22] bg-[#111113] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-[#fafafa]">
                {isTr ? "Haftalık Sorgu Hacmi" : "Weekly Query Volume"}
              </div>
              <div className="text-xs text-[#71717a] mt-0.5">
                {isTr ? "Analist çalıştırma sorguları" : "Analyst execution queries"}
              </div>
            </div>
            <span className="text-[11px] font-mono text-[#22c55e] font-semibold bg-[#22c55e]/10 px-2 py-0.5 rounded">
              {isTr ? "Aktif" : "Active"}
            </span>
          </div>

          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={QUERY_VOLUME_DATA} barSize={18} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="#1f1f22" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="day" tick={{ fill: "#52525b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#52525b", fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="queries" fill="#6366f1" radius={[4, 4, 0, 0]} opacity={0.85} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Section: Recent Analyses + Recent Datasets */}
      <div className="grid-2">
        {/* Recent Analyses Feed */}
        <div className="rounded-xl border border-[#1f1f22] bg-[#111113] overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#1f1f22] px-5 py-3.5">
            <span className="text-sm font-semibold text-[#fafafa]">
              {isTr ? "Son AI Analizleri" : "Recent AI Analyses"}
            </span>
            <Link
              href="/executions"
              className="flex items-center gap-1 text-xs font-medium text-[#818cf8] hover:text-[#a5b4fc]"
            >
              {isTr ? "Tümünü gör" : "View all"} <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-[#1f1f22]">
            {RECENT_ANALYSES.map((a) => (
              <div key={a.id} className="flex items-center gap-3 px-5 py-3 hover:bg-[#18181b]/50 transition-colors">
                <div
                  className={`h-2 w-2 rounded-full shrink-0 ${
                    a.status === "running" ? "animate-pulse-dot" : ""
                  }`}
                  style={{ backgroundColor: STATUS_COLOR[a.status] }}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-[#fafafa] truncate">
                    {isTr ? a.titleTr : a.title}
                  </div>
                  <div className="text-[10px] text-[#52525b] mt-0.5">
                    {isTr
                      ? `${a.sources} kaynak bağlandı · ${a.timeTr}`
                      : `${a.sources} sources linked · ${a.time}`}
                  </div>
                </div>
                <button
                  onClick={() => router.push("/analyst")}
                  className="rounded border border-[#6366f1]/30 bg-[#6366f1]/10 px-2.5 py-1 text-[11px] font-semibold text-[#818cf8] hover:bg-[#6366f1]/20 transition-colors cursor-pointer shrink-0"
                >
                  {isTr ? "Aç" : "Open"}
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Indexed Documents */}
        <div className="rounded-xl border border-[#1f1f22] bg-[#111113] overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#1f1f22] px-5 py-3.5">
            <span className="text-sm font-semibold text-[#fafafa]">
              {isTr ? "İndekslenen Veri Setleri & Belgeler" : "Indexed Datasets & Documents"}
            </span>
            <Link
              href="/datasets"
              className="flex items-center gap-1 text-xs font-medium text-[#818cf8] hover:text-[#a5b4fc]"
            >
              {isTr ? "Yönet" : "Manage"} <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          <div className="divide-y divide-[#1f1f22]">
            {RECENT_DOCS.map((doc) => {
              const isSheet = doc.name.endsWith(".xlsx") || doc.name.endsWith(".csv");
              const Icon = isSheet ? FileSpreadsheet : FileText;
              const statusDisplay =
                doc.status === "ready"
                  ? isTr ? "hazır" : "ready"
                  : doc.status === "processing"
                  ? isTr ? "işleniyor" : "processing"
                  : isTr ? "hata" : "failed";
              return (
                <div key={doc.id} className="flex items-center gap-3 px-5 py-3 hover:bg-[#18181b]/50 transition-colors">
                  <div
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
                    style={{
                      backgroundColor: isSheet ? "rgba(34,197,94,0.12)" : "rgba(99,102,241,0.12)",
                      color: isSheet ? "#22c55e" : "#818cf8",
                    }}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium text-[#fafafa] truncate">{doc.name}</div>
                    <div className="text-[10px] text-[#52525b] mt-0.5">
                      {doc.size} {doc.pages ? (isTr ? `· ${doc.pages} sayfa` : `· ${doc.pages} pages`) : ""}
                    </div>
                  </div>
                  <span
                    className="rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider shrink-0"
                    style={{
                      backgroundColor: `${STATUS_COLOR[doc.status]}15`,
                      color: STATUS_COLOR[doc.status],
                    }}
                  >
                    {statusDisplay}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Quick Actions Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-xl border border-[#6366f1]/20 bg-gradient-to-r from-[#6366f1]/[0.08] to-[#22d3ee]/[0.04] p-5">
        <div>
          <div className="text-sm font-semibold text-[#fafafa]">
            {isTr ? "Kurumsal Hızlı Eylemler" : "Enterprise Quick Actions"}
          </div>
          <div className="text-xs text-[#71717a] mt-0.5">
            {isTr
              ? "Araştırma sorgusu başlatın, bilgi veri setlerini içeri aktarın veya FinOps harcamalarını denetleyin"
              : "Launch research query, onboard knowledge datasets, or inspect FinOps spend"}
          </div>
        </div>
        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={() => router.push("/analyst")}
            className="flex items-center gap-2 rounded-lg bg-[#6366f1] px-3.5 py-2 text-xs font-semibold text-white shadow-md shadow-[#6366f1]/30 hover:bg-[#818cf8] transition-all cursor-pointer"
          >
            <Bot className="h-4 w-4" />
            <span>{isTr ? "AI Analiste Sor" : "Ask AI Analyst"}</span>
          </button>
          <button
            onClick={() => router.push("/datasets")}
            className="flex items-center gap-2 rounded-lg border border-[#27272a] bg-[#18181b] px-3.5 py-2 text-xs font-medium text-[#a1a1aa] hover:border-[#3f3f46] hover:text-[#fafafa] transition-colors cursor-pointer"
          >
            <Upload className="h-4 w-4" />
            <span>{isTr ? "Veri Seti Yükle" : "Upload Dataset"}</span>
          </button>
          <button
            onClick={() => router.push("/finops")}
            className="flex items-center gap-2 rounded-lg border border-[#27272a] bg-[#18181b] px-3.5 py-2 text-xs font-medium text-[#a1a1aa] hover:border-[#3f3f46] hover:text-[#fafafa] transition-colors cursor-pointer"
          >
            <Coins className="h-4 w-4" />
            <span>{isTr ? "FinOps Merkezi" : "FinOps Hub"}</span>
          </button>
          <button
            onClick={() => router.push("/operations")}
            className="flex items-center gap-2 rounded-lg border border-[#27272a] bg-[#18181b] px-3.5 py-2 text-xs font-medium text-[#a1a1aa] hover:border-[#3f3f46] hover:text-[#fafafa] transition-colors cursor-pointer"
          >
            <Activity className="h-4 w-4" />
            <span>{isTr ? "Operasyonlar & SLO" : "Operations & SLO"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
