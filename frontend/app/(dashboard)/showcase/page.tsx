"use client";

import React from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Bot,
  ShieldCheck,
  Activity,
  Coins,
  ArrowRight,
  GitBranch,
  Terminal,
  Play,
  Cpu,
  Lock,
  Workflow,
} from "lucide-react";
import { useLanguage } from "@/contexts/language-context";

export default function ShowcasePage() {
  const router = useRouter();
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  const handleLaunchDemo = () => {
    router.push("/analyst");
  };

  const ARCHITECTURE_LAYERS = [
    {
      title: isTr ? "1. İstemci & Sunum Katmanı" : "1. Client & Presentation Layer",
      subtitle: "Next.js 16 (App Router) · React 19 · Turbopack · Tailwind v4 · Recharts",
      description: isTr
        ? "Gerçek zamanlı SSE akışı, aşamalı düşünce durumu zaman çizelgesi, etkileşimli kaynak alıntıları ([S1], [D1]) ve ⌘K Komut Paleti içeren iki dilli (TR/EN) duyarlı araştırma çalışma alanı."
        : "Bilingual (EN/TR) responsive research workspace featuring real-time SSE streaming, progressive thinking state timeline, interactive citation provenance ([S1], [D1]), and ⌘K Command Palette.",
      color: "#6366f1",
      icon: Sparkles,
      tags: ["Next.js 16", "Turbopack", "React 19", "SSE Protocol", "Recharts", "Lucide"],
    },
    {
      title: isTr ? "2. API Ağ Geçidi & Telemetri Katmanı" : "2. API Gateway & Telemetry Layer",
      subtitle: "FastAPI · W3C Distributed Tracing · Token Bucket Rate Limiting · HttpOnly CSRF",
      description: isTr
        ? "Çok kiracılı izolasyonu (X-Organization-ID), yapılandırılmış hata bildirimlerini, STRIDE tehdit korumalarını, Prometheus metriklerini ve OpenTelemetry izlerini uygulayan merkezi ağ geçidi."
        : "Centralized gateway enforcing multi-tenant isolation (X-Organization-ID), structured error envelopes, STRIDE threat protections, Prometheus metrics, and OpenTelemetry spans.",
      color: "#22d3ee",
      icon: Lock,
      tags: ["FastAPI", "OpenTelemetry", "Prometheus", "Pydantic v2", "OAuth2/JWT", "W3C Trace"],
    },
    {
      title: isTr ? "3. Hibrit Zekâ & Ajan Çalışma Zamanı" : "3. Hybrid Intelligence & Agent Runtime",
      subtitle: "Dense/Sparse RAG · AST Text-to-SQL · Knowledge Graph · 10-State Agent FSM",
      description: isTr
        ? "Paralel RAG (BM25 + Vektör RRF füzyonu), salt-okunur AST doğrulamalı SQL, sınırlı bilgi grafı geçişleri ve çok boyutlu token bütçeli durum makineli ajan yürütmesi."
        : "Multi-modal reasoning engine executing parallel RAG (BM25 + Dense vector RRF fusion), read-only AST-validated SQL, bounded graph traversals, and checkpointed agent execution with multi-dimensional token budgets.",
      color: "#22c55e",
      icon: Workflow,
      tags: ["Hybrid RAG (RRF)", "AST SQL Guard", "Knowledge Graph", "Agent FSM", "Checkpoints"],
    },
    {
      title: isTr ? "4. Altyapı, SRE & FinOps Temeli" : "4. Infrastructure, SRE & FinOps Foundation",
      subtitle: "PostgreSQL 16 · Redis 7 · Qdrant Vector DB · Chaos Fault Injection · Cost Ledger",
      description: isTr
        ? "Sıfır halüsinasyonlu alıntı kökeni, SLO hata bütçesi takibi, otomatik kaos kurtarma doğrulaması, insan onay mekanizmaları ve istek başına değiştirilemez FinOps maliyet defteri."
        : "Zero-hallucination citation provenance, SLO error budget tracking, automated chaos recovery validation, human approval quorums, and immutable per-request FinOps cost attribution ledger.",
      color: "#f59e0b",
      icon: Cpu,
      tags: ["PostgreSQL 16", "Redis 7", "Qdrant", "SLO Burn Rate", "FinOps Ledger", "Chaos Engine"],
    },
  ];

  const CAPABILITY_PILLARS = [
    {
      title: isTr ? "Doğrulanmış Çok Modlu Yapay Zekâ" : "Grounded Multi-Modal AI",
      description: isTr
        ? "Yapılandırılmış SQL kayıtlarını, yapılandırılmamış vektör belgelerini ve varlık ilişki graflarını tıklanabilir kaynak kanıtlarıyla ([S1], [D1]) tek ve tutarlı bir yanıtta sentezler."
        : "Synthesizes structured SQL records, unstructured vector documents, and entity relationship graphs into a single coherent answer with clickable provenance citations [S1], [D1].",
      icon: Bot,
      color: "#6366f1",
      metric: isTr ? "%94.7 Doğrulanabilirlik" : "94.7% Groundedness",
    },
    {
      title: isTr ? "Üretim SRE & Güvenilirlik" : "Production SRE & Reliability",
      description: isTr
        ? "Otomatik SLO takibi, hata bütçesi tükenme hızları, uyarı yaşam döngüsü FSM'si ve veritabanı ile ağ geçidi arızalarında hızlı kurtarmayı kanıtlayan kaos dayanıklılık senaryoları."
        : "Automated SLO tracking, error budget burn rates, alert lifecycle FSM, and chaos resilience scenarios proving rapid recovery under database and gateway failure.",
      icon: Activity,
      color: "#22d3ee",
      metric: isTr ? "%99.95 Erişilebilirlik" : "99.95% Availability",
    },
    {
      title: isTr ? "Kurumsal Yönetişim & Çoğunluk Onayı" : "Enterprise Governance & Quorum",
      description: isTr
        ? "Hassas sorgular için insan onay iş akışları, kriptografik köken karmaları, otomatik veri sınıflandırma rozetleri ve değiştirilemez denetim izleri."
        : "Human-in-the-loop approval workflows for sensitive queries, cryptographic provenance hashes, automated data classification badges, and immutable audit trails.",
      icon: ShieldCheck,
      color: "#22c55e",
      metric: isTr ? "Sıfır Güven RBAC" : "Zero-Trust RBAC",
    },
    {
      title: isTr ? "FinOps Maliyet Yönetişimi" : "FinOps Cost Governance",
      description: isTr
        ? "Gerçek zamanlı belirteç kullanım takibi, çoklu sağlayıcı model fiyatlandırması, bütçe üst sınırları, anomali tespiti ve harcama mutabakatı."
        : "Real-time token usage tracking, multi-provider model pricing, budget hard-capping, anomaly detection, and spend reconciliation.",
      icon: Coins,
      color: "#f59e0b",
      metric: isTr ? "Gerçek Zamanlı Maliyet Defteri" : "Real-time Ledger",
    },
  ];

  return (
    <div className="page-pad mx-auto max-w-7xl space-y-8 animate-fade-in">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-[#27272a] bg-gradient-to-br from-[#111113] via-[#141418] to-[#0d0d0f] p-6 sm:p-10 shadow-2xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-[#6366f1]/30 bg-[#6366f1]/10 px-3 py-1 text-xs font-semibold text-[#a5b4fc]">
            <Sparkles className="h-3.5 w-3.5 text-[#818cf8]" />
            <span>{isTr ? "Sistem & Platform Mimarisi" : "System & Platform Architecture"}</span>
          </div>

          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight text-[#fafafa] leading-tight">
            Enterprise AI Analyst
          </h1>

          <p className="text-sm sm:text-base text-[#a1a1aa] leading-relaxed">
            {isTr
              ? "Hibrit RAG, deterministik Metinden-SQL'e dönüşüm, bilgi grafları ve ajan orkestrasyonunu kurumsal yönetişim, SRE güvenilirliği ve FinOps maliyet tahsisiyle birleştiren üretim sınıfı Kurumsal Yapay Zekâ Analist platformu."
              : "A production-grade Enterprise AI intelligence platform connecting hybrid RAG, deterministic Text-to-SQL, knowledge graphs, and agent orchestration with production-grade governance, SRE reliability, and FinOps cost attribution."}
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              onClick={handleLaunchDemo}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#6366f1] to-[#4f46e5] px-5 py-2.5 text-xs sm:text-sm font-bold text-white shadow-lg shadow-[#6366f1]/30 hover:brightness-110 transition-all cursor-pointer"
            >
              <Play className="h-4 w-4 fill-current" />
              <span>{isTr ? "Canlı Yapay Zekâ Analist Demosunu Başlat" : "Launch Live AI Analyst Demo"}</span>
              <ArrowRight className="h-4 w-4" />
            </button>

            <a
              href="https://github.com"
              target="_blank"
              rel="noreferrer"
              className="flex items-center gap-2 rounded-xl border border-[#27272a] bg-[#18181b] px-4 py-2.5 text-xs sm:text-sm font-semibold text-[#e4e4e7] hover:border-[#3f3f46] hover:text-white transition-colors cursor-pointer"
            >
              <GitBranch className="h-4 w-4" />
              <span>{isTr ? "GitHub Deposu" : "GitHub Repository"}</span>
            </a>
          </div>
        </div>

        {/* Decorative background glow */}
        <div
          className="absolute -right-20 -top-20 h-96 w-96 rounded-full opacity-20 blur-3xl pointer-events-none"
          style={{
            background: "radial-gradient(circle, #6366f1 0%, #22d3ee 100%)",
          }}
        />
      </div>

      {/* 4 Pillars of the Platform */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
            {isTr ? "Mimari Temel Direkler" : "Architectural Pillars"}
          </h2>
          <span className="text-xs text-[#71717a]">
            {isTr ? "TASK 0 → TASK 42 arasında mühendislikle inşa edildi" : "Engineered from TASK 0 → TASK 42"}
          </span>
        </div>

        <div className="grid-4">
          {CAPABILITY_PILLARS.map((pillar) => {
            const Icon = pillar.icon;
            return (
              <div
                key={pillar.title}
                className="rounded-xl border border-[#1f1f22] bg-[#111113] p-5 flex flex-col justify-between space-y-3 hover:border-[#27272a] transition-all"
              >
                <div className="flex items-center justify-between">
                  <div
                    className="flex h-8 w-8 items-center justify-center rounded-lg"
                    style={{
                      backgroundColor: `${pillar.color}15`,
                      color: pillar.color,
                    }}
                  >
                    <Icon className="h-4 w-4" />
                  </div>
                  <span
                    className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full"
                    style={{
                      backgroundColor: `${pillar.color}15`,
                      color: pillar.color,
                    }}
                  >
                    {pillar.metric}
                  </span>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-[#fafafa]">{pillar.title}</h3>
                  <p className="text-xs text-[#71717a] mt-1 leading-relaxed">
                    {pillar.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Layer-by-Layer System Architecture */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-[#fafafa] tracking-tight">
              {isTr ? "Uçtan Uca Sistem Mimarisi Katmanları" : "Full-Stack Architecture Layers"}
            </h2>
            <p className="text-xs text-[#71717a] mt-0.5">
              {isTr ? "Sıfır atlama ile 4 kademeli katı sorumluluk ayrımı" : "Strict 4-tier separation of concerns with zero bypasses"}
            </p>
          </div>
          <span className="font-mono text-xs text-[#818cf8]">
            {isTr ? "288 Arka Yüz Testi · 25 UI Testi" : "288 Backend Tests · 25 UI Tests"}
          </span>
        </div>

        <div className="space-y-3">
          {ARCHITECTURE_LAYERS.map((layer, index) => {
            const Icon = layer.icon;
            return (
              <div
                key={layer.title}
                className="rounded-xl border border-[#1f1f22] bg-[#111113] p-5 hover:border-[#27272a] transition-all space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <div
                      className="flex h-7 w-7 items-center justify-center rounded-lg shrink-0"
                      style={{
                        backgroundColor: `${layer.color}15`,
                        color: layer.color,
                      }}
                    >
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-[#fafafa]">{layer.title}</h3>
                      <span className="text-[11px] font-mono text-[#71717a]">
                        {layer.subtitle}
                      </span>
                    </div>
                  </div>

                  <span className="text-xs font-mono text-[#52525b]">Layer 0{index + 1}</span>
                </div>

                <p className="text-xs text-[#a1a1aa] leading-relaxed">
                  {layer.description}
                </p>

                <div className="flex flex-wrap gap-1.5 pt-1">
                  {layer.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded border border-[#27272a] bg-[#18181b] px-2 py-0.5 text-[10px] font-mono text-[#a1a1aa]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Canonical Killer Demo Scenario Box */}
      <div className="rounded-xl border border-[#6366f1]/30 bg-gradient-to-br from-[#6366f1]/10 via-[#111113] to-[#18181b] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-[#818cf8]" />
            <span className="text-xs font-bold uppercase tracking-wider text-[#a5b4fc]">
              {isTr ? "Kanonik Demo Senaryosu" : "Canonical Demo Scenario"}
            </span>
          </div>
          <span className="rounded bg-[#22c55e]/15 px-2 py-0.5 text-[10px] font-mono font-bold text-[#22c55e]">
            {isTr ? "Deterministik Tohum Aktif" : "Deterministic Seed Active"}
          </span>
        </div>

        <div className="rounded-lg border border-[#27272a] bg-[#09090b] p-3 text-xs font-mono text-[#e4e4e7] leading-relaxed">
          {isTr
            ? "\"Kurumsal ARR büyümesine rağmen Kuzey Amerika'da 3. çeyrek işletme marjının neden daraldığını açıklayın, mali defter kayıtlarıyla doğrulayın ve müşteri kaybı risklerini özetleyin.\""
            : "\"Explain why Q3 operating margin contracted in North America despite enterprise ARR growth, verify with ledger records, and outline customer churn risks.\""}
        </div>

        <div className="grid-3 pt-1">
          <div className="text-[11px] text-[#71717a]">
            <span className="font-semibold text-[#fafafa]">{isTr ? "1. Çok Modlu Dallanma:" : "1. Multi-Modal Branching:"}</span>
            {isTr
              ? " Postgres defteri üzerinde paralel AST SQL çalıştırma + SEC 10-Q raporu üzerinde Hibrit RAG."
              : " Parallel AST SQL execution on Postgres ledger + Hybrid RAG over SEC 10-Q filing."}
          </div>
          <div className="text-[11px] text-[#71717a]">
            <span className="font-semibold text-[#fafafa]">{isTr ? "2. Kanıt Alıntıları:" : "2. Evidence Citations:"}</span>
            {isTr
              ? " [S1] ve [D1] köken etiketlerine doğrudan bağlantı ve alıntı doğrulama."
              : " Direct linking to provenance tags [S1] and [D1] with excerpt verification."}
          </div>
          <div className="text-[11px] text-[#71717a]">
            <span className="font-semibold text-[#fafafa]">{isTr ? "3. FinOps & Denetim:" : "3. FinOps & Audit:"}</span>
            {isTr
              ? " Değiştirilemez organizasyon defterine kaydedilen gerçek zamanlı belirteç tüketim maliyeti."
              : " Real-time token consumption cost recorded into immutable organization ledger."}
          </div>
        </div>

        <div className="pt-2">
          <button
            onClick={handleLaunchDemo}
            className="flex items-center gap-2 rounded-lg bg-[#6366f1] px-4 py-2 text-xs font-bold text-white shadow-md shadow-[#6366f1]/30 hover:bg-[#818cf8] transition-colors cursor-pointer"
          >
            <Play className="h-3.5 w-3.5 fill-current" />
            <span>{isTr ? "Senaryoyu Yapay Zekâ Analist Çalışma Alanında Yürüt" : "Execute Scenario in AI Analyst Workspace"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
