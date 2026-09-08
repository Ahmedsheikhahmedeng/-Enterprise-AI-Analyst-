import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { Providers } from "@/lib/query/providers";
import { AuthProvider } from "@/features/auth/auth-context";

// Mock next/navigation
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe("Dynamic Multi-Language Toggle (EN <-> TR)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("toggles between English and Turkish dynamically across Sidebar and Topbar", () => {
    render(
      <Providers>
        <AuthProvider>
          <div>
            <Topbar onOpenCommandPalette={vi.fn()} />
            <Sidebar />
          </div>
        </AuthProvider>
      </Providers>
    );

    // 1. Verify default is English
    expect(screen.getByText("AI Analyst")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Search workspace...")).toBeInTheDocument();
    expect(screen.getByText("TR")).toBeInTheDocument();

    // 2. Click language switcher button to switch to Turkish
    const trButton = screen.getByText("TR").closest("button");
    expect(trButton).not.toBeNull();
    fireEvent.click(trButton!);

    // 3. Verify elements immediately update to Turkish
    expect(screen.getByText("AI Analist")).toBeInTheDocument();
    expect(screen.getByText("Operasyonlar")).toBeInTheDocument();
    expect(screen.getByText("Çalışma alanında ara...")).toBeInTheDocument();
    expect(screen.getByText("EN")).toBeInTheDocument();

    // 4. Click again to switch back to English
    const enButton = screen.getByText("EN").closest("button");
    expect(enButton).not.toBeNull();
    fireEvent.click(enButton!);

    // 5. Verify elements returned to English
    expect(screen.getByText("AI Analyst")).toBeInTheDocument();
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("Search workspace...")).toBeInTheDocument();
    expect(screen.getByText("TR")).toBeInTheDocument();
  });

  it("renders deep pages in Turkish when language is set to TR", async () => {
    localStorage.setItem("enterprise_lang", "tr");

    const { default: SemanticPage } = await import("@/app/(dashboard)/semantic/page");
    const { default: SettingsPage } = await import("@/app/(dashboard)/settings/page");
    const { default: ShowcasePage } = await import("@/app/(dashboard)/showcase/page");
    const { default: DatasetsPage } = await import("@/app/(dashboard)/datasets/page");
    const { default: ExecutionsPage } = await import("@/app/(dashboard)/executions/page");
    const { default: ApprovalsPage } = await import("@/app/(dashboard)/approvals/page");
    const { default: EvaluationPage } = await import("@/app/(dashboard)/evaluation/page");

    render(
      <Providers>
        <AuthProvider>
          <div>
            <SemanticPage />
            <SettingsPage />
            <ShowcasePage />
            <DatasetsPage />
            <ExecutionsPage />
            <ApprovalsPage />
            <EvaluationPage />
          </div>
        </AuthProvider>
      </Providers>
    );

    // Semantic page in Turkish
    expect(screen.getByText("Semantik Katman & Kurumsal Bilgi Grafı")).toBeInTheDocument();
    expect(screen.getByText("İş Terimleri Sözlüğü")).toBeInTheDocument();
    expect(screen.getByText("Hesaplanan Metrikler & Formüller")).toBeInTheDocument();

    // Settings page in Turkish
    expect(screen.getByText("Çalışma Alanı Yapılandırması & Güvenlik")).toBeInTheDocument();
    expect(screen.getByText("Kullanıcı Profili")).toBeInTheDocument();
    expect(screen.getByText("Oturumu Kapat")).toBeInTheDocument();

    // Showcase page in Turkish
    expect(screen.getByText("Sistem & Platform Mimarisi")).toBeInTheDocument();
    expect(screen.getByText("Canlı Yapay Zekâ Analist Demosunu Başlat")).toBeInTheDocument();
    expect(screen.getByText("Mimari Temel Direkler")).toBeInTheDocument();

    // Datasets page in Turkish
    expect(screen.getByText("Kurumsal Veri Setleri & Soykütüğü Kataloğu")).toBeInTheDocument();

    // Executions page in Turkish
    expect(screen.getByText("Çalıştırma Denetim Geçmişi")).toBeInTheDocument();

    // Approvals page in Turkish
    expect(screen.getByText("Yönetişim & İnsan Onay Kuyruğu")).toBeInTheDocument();

    // Evaluation page in Turkish
    expect(screen.getByText("Sürekli AI Kalitesi & Kıyaslama Takibi")).toBeInTheDocument();
  });
});
