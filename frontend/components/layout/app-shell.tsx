"use client";

import React, { useState } from "react";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";
import { CommandPalette } from "./command-palette";
import { X } from "lucide-react";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#09090b] text-[#fafafa]">
      {/* Desktop Collapsible Sidebar */}
      <Sidebar className="hidden md:flex" />

      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-xs"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative z-50 flex w-68 max-w-xs flex-1 flex-col bg-[#0d0d0f] shadow-2xl border-r border-[#1a1a1d]">
            <div className="absolute right-2 top-3 z-10">
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1 rounded-md text-[#71717a] hover:text-[#fafafa] hover:bg-[#18181b] transition-colors cursor-pointer"
                aria-label="Close navigation"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <Sidebar isMobile onItemClick={() => setMobileMenuOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        <Topbar
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          onOpenCommandPalette={() => setCommandPaletteOpen(true)}
        />
        <main className="flex-1 overflow-y-auto page-transition">{children}</main>
      </div>

      {/* Global ⌘K Command Palette */}
      <CommandPalette
        open={commandPaletteOpen}
        onClose={() => setCommandPaletteOpen(false)}
      />
    </div>
  );
}
