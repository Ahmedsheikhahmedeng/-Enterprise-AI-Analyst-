"use client";

import React from "react";
import { useAuth } from "@/features/auth/auth-context";
import { Settings, ShieldCheck, User, Building2, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/language-context";

export default function SettingsPage() {
  const { user, activeOrgName, activeOrgId, logout } = useAuth();
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-2.5 border-b border-border/80 pb-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-muted text-muted-foreground">
          <Settings className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-foreground">
            {isTr ? "Çalışma Alanı Yapılandırması & Güvenlik" : "Workspace Configuration & Security"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "Kiracı sınırları, kimliği doğrulanmış profil ayrıntıları ve yönetişim ilkeleri."
              : "Tenant boundaries, authenticated profile details, and governance policies."}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* User Profile Card */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center gap-2 border-b border-border/70 pb-2.5">
            <User className="h-4 w-4 text-primary" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              {isTr ? "Kullanıcı Profili" : "User Profile"}
            </h3>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-muted-foreground">{isTr ? "Ad Soyad:" : "Name:"}</span>
              <span className="font-semibold text-foreground">{user?.full_name}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-muted-foreground">{isTr ? "E-posta:" : "Email:"}</span>
              <span className="font-mono text-foreground">{user?.email}</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-muted-foreground">{isTr ? "Rol:" : "Role:"}</span>
              <span className="font-mono font-bold text-primary">{user?.role}</span>
            </div>
          </div>
        </div>

        {/* Active Organization Card */}
        <div className="rounded-xl border border-border bg-card p-5 space-y-3">
          <div className="flex items-center gap-2 border-b border-border/70 pb-2.5">
            <Building2 className="h-4 w-4 text-primary" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
              {isTr ? "Kiracı Sınırı" : "Tenant Boundary"}
            </h3>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-muted-foreground">{isTr ? "Kiracı Adı:" : "Tenant Name:"}</span>
              <span className="font-semibold text-foreground">{activeOrgName}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-muted-foreground">{isTr ? "Kiracı UUID:" : "Tenant UUID:"}</span>
              <span className="font-mono text-[11px] text-muted-foreground truncate max-w-[180px]">
                {activeOrgId}
              </span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-muted-foreground">{isTr ? "İzolasyon Modu:" : "Isolation Mode:"}</span>
              <span className="font-mono text-emerald-600 font-semibold">STRICT_ROW_LEVEL</span>
            </div>
          </div>
        </div>
      </div>

      {/* Security Checkpoints Card */}
      <div className="rounded-xl border border-border bg-card p-5 space-y-3">
        <div className="flex items-center gap-2 border-b border-border/70 pb-2.5">
          <Lock className="h-4 w-4 text-emerald-500" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">
            {isTr ? "Güvenlik & Yönetişim Koruma Hatları" : "Security & Governance Guardrails"}
          </h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          <div className="flex items-start gap-2 rounded-lg bg-muted/30 p-2.5">
            <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-foreground">
                {isTr ? "Sıfır Token Depolama" : "Zero Token Storage"}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {isTr
                  ? "Hassas erişim belirteçleri localStorage'da saklanmaz; HttpOnly çerezlerle korunur."
                  : "Sensitive access tokens never stored in localStorage; secured with HttpOnly cookies."}
              </div>
            </div>
          </div>

          <div className="flex items-start gap-2 rounded-lg bg-muted/30 p-2.5">
            <ShieldCheck className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold text-foreground">
                {isTr ? "CSRF Çift Gönderim Koruması" : "CSRF Double-Submit Protection"}
              </div>
              <div className="text-[11px] text-muted-foreground">
                {isTr
                  ? "Durum değiştiren istekler, eşleşen X-CSRF-Token başlıkları ile sıkı bir şekilde doğrulanır."
                  : "State-modifying requests strictly verified with matching X-CSRF-Token headers."}
              </div>
            </div>
          </div>
        </div>

        <div className="pt-3 border-t border-border flex justify-end">
          <Button variant="destructive" size="sm" onClick={logout} className="text-xs">
            {isTr ? "Oturumu Kapat" : "Log Out Session"}
          </Button>
        </div>
      </div>
    </div>
  );
}
