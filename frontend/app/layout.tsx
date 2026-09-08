import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/lib/query/providers";
import { AuthProvider } from "@/features/auth/auth-context";

export const metadata: Metadata = {
  title: "Enterprise AI Analyst Platform",
  description: "Production-grade multi-agent financial and operational AI analyst workspace with real-time SSE streaming, verifiable citations, and governance quality gates.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-foreground antialiased selection:bg-primary/20 selection:text-primary">
        <Providers>
          <AuthProvider>{children}</AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
