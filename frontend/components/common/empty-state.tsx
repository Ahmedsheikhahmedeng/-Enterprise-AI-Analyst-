import React from "react";
import { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-border/80 p-8 text-center bg-card/30">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground mb-3">
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="text-sm font-semibold text-foreground mb-1">{title}</h3>
      <p className="max-w-xs text-xs text-muted-foreground mb-4 leading-normal">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button size="sm" variant="outline" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
