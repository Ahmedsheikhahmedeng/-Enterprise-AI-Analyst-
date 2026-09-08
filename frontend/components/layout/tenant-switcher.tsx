"use client";

import React, { useState } from "react";
import { Building2, ChevronDown, Check } from "lucide-react";
import { useAuth } from "@/features/auth/auth-context";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";

export function TenantSwitcher() {
  const { user, activeOrgId, activeOrgName, switchOrganization } = useAuth();
  const [open, setOpen] = useState(false);

  const orgs = user?.available_organizations || [
    { id: activeOrgId || "default-org", name: activeOrgName || "Primary Organization" },
  ];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="h-8 gap-2 bg-background/50 border-border/60 text-xs font-medium text-foreground hover:bg-accent"
        >
          <Building2 className="h-3.5 w-3.5 text-primary" />
          <span className="max-w-[120px] truncate">{activeOrgName || "Organization"}</span>
          <ChevronDown className="h-3 w-3 text-muted-foreground opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-1.5" align="start">
        <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
          Switch Organization
        </div>
        <div className="space-y-1">
          {orgs.map((org) => {
            const isSelected = org.id === activeOrgId;
            return (
              <button
                key={org.id}
                onClick={() => {
                  switchOrganization(org.id, org.name);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors ${
                  isSelected
                    ? "bg-primary/10 text-primary font-semibold"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <Building2 className="h-3.5 w-3.5 shrink-0 opacity-70" />
                  <span className="truncate">{org.name}</span>
                </div>
                {isSelected && <Check className="h-3.5 w-3.5 shrink-0 text-primary" />}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}
