"use client";

import React from "react";
import { TenantSwitcher } from "./tenant-switcher";
import { ThemeToggle } from "./theme-toggle";
import { useAuth } from "@/features/auth/auth-context";
import { User, LogOut, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Header({
  onOpenMobileMenu,
}: {
  onOpenMobileMenu?: () => void;
}) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-14 w-full items-center justify-between border-b border-border/80 bg-background/80 px-4 backdrop-blur-md">
      <div className="flex items-center gap-3">
        {onOpenMobileMenu && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onOpenMobileMenu}
            className="md:hidden"
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
        )}
        <TenantSwitcher />
      </div>

      <div className="flex items-center gap-2">
        <ThemeToggle />

        {/* User Profile Pill */}
        <div className="flex items-center gap-2 border-l border-border/80 pl-2">
          <div className="flex items-center gap-1.5 rounded-full bg-muted/60 py-1 pl-2 pr-2.5 text-xs text-foreground">
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary/20 text-primary">
              <User className="h-3 w-3" />
            </div>
            <span className="max-w-[100px] truncate font-medium sm:max-w-[150px]">
              {user?.full_name || "Analyst"}
            </span>
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={logout}
            title="Log out"
            aria-label="Log out"
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
          >
            <LogOut className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </header>
  );
}
