"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/features/auth/auth-context";
import { BrainCircuit, ShieldCheck, ArrowRight } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/language-context";

export default function LoginPage() {
  const [username, setUsername] = useState("analyst@enterprise.internal");
  const [password, setPassword] = useState("••••••••••••");
  const [error, setError] = useState<string | null>(null);
  const { login, isLoading } = useAuth();
  const router = useRouter();
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await login(username, password);
      router.push("/analyst");
    } catch {
      setError(
        isTr
          ? "Geçersiz kurumsal kimlik bilgileri veya oturum süresi doldu."
          : "Invalid enterprise credentials or session expired."
      );
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-6 rounded-2xl border border-border bg-card p-8 shadow-xl">
        {/* Brand */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <BrainCircuit className="h-6 w-6" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">
            Enterprise AI Analyst
          </h1>
          <p className="text-xs text-muted-foreground">
            {isTr
              ? "Tekil Oturum Açma (SSO) & Çok Kiracılı Doğrulanmış Çalışma Alanı"
              : "Single Sign-On & Multi-Tenant Verified Workspace"}
          </p>
        </div>

        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive text-center">
            {error}
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              {isTr ? "Kurumsal Kullanıcı Adı veya E-posta" : "Enterprise Username or Email"}
            </label>
            <Input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="text-xs"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-semibold text-foreground">
              {isTr ? "Şifre" : "Password"}
            </label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="text-xs"
            />
          </div>

          <Button
            type="submit"
            disabled={isLoading}
            className="w-full h-9 gap-2 text-xs font-semibold shadow-sm"
          >
            <span>{isTr ? "Çalışma Alanına Giriş Yap" : "Sign In to Workspace"}</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        </form>

        <div className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground pt-2 border-t border-border">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
          <span>
            {isTr
              ? "Sıkı Sıfır-Sızıntı & Yönetişim Korumalı"
              : "Strict Zero-Leakage & Governance Protected"}
          </span>
        </div>
      </div>
    </div>
  );
}
