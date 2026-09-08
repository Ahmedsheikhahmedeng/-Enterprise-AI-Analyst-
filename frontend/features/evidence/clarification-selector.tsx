"use client";

import React from "react";
import { HelpCircle, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ClarificationSelectorProps {
  options: string[];
  onSelectOption: (option: string) => void;
}

export function ClarificationSelector({
  options,
  onSelectOption,
}: ClarificationSelectorProps) {
  if (!options || options.length === 0) return null;

  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 my-3 space-y-3">
      <div className="flex items-center gap-2 text-primary font-semibold text-xs">
        <HelpCircle className="h-4 w-4" />
        <span>Clarification Required: Please specify the intended metric or scope</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {options.map((option, idx) => (
          <Button
            key={idx}
            variant="outline"
            size="sm"
            onClick={() => onSelectOption(option)}
            className="justify-between bg-card hover:bg-primary/10 border-border text-xs h-auto py-2 px-3 text-left font-normal"
          >
            <span className="truncate">{option}</span>
            <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0 ml-2" />
          </Button>
        ))}
      </div>
    </div>
  );
}
