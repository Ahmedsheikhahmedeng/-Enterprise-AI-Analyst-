"use client";

import React, { useState } from "react";
import { ApprovalItem } from "@/types/platform";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ShieldAlert, Check, X } from "lucide-react";

interface ApprovalDialogProps {
  item: ApprovalItem | null;
  open: boolean;
  onClose: () => void;
  onResolve: (id: string, decision: "APPROVED" | "REJECTED", comment?: string) => Promise<void>;
}

export function ApprovalDialog({
  item,
  open,
  onClose,
  onResolve,
}: ApprovalDialogProps) {
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!item) return null;

  const handleAction = async (decision: "APPROVED" | "REJECTED") => {
    setIsSubmitting(true);
    try {
      await onResolve(item.id, decision, comment);
      setComment("");
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
            <ShieldAlert className="h-5 w-5" />
            <DialogTitle>Governance Approval Decision</DialogTitle>
          </div>
          <DialogDescription className="text-xs">
            A high-impact query or execution action requires formal compliance sign-off.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2 text-xs">
          <div className="rounded-lg bg-muted/60 p-3 space-y-1.5 border border-border">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Action Type:</span>
              <span className="font-semibold text-foreground">{item.action_type}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Risk Level:</span>
              <span className="font-bold text-rose-600">{item.risk_level}</span>
            </div>
            {item.reason && (
              <div className="pt-1 text-muted-foreground">
                <span className="font-medium text-foreground">Trigger Reason: </span>
                {item.reason}
              </div>
            )}
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-medium text-foreground">
              Audit Comment / Justification:
            </label>
            <Textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Enter compliance justification or rejection reason..."
              className="text-xs min-h-[70px]"
            />
          </div>
        </div>

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="destructive"
            size="sm"
            disabled={isSubmitting}
            onClick={() => handleAction("REJECTED")}
            className="gap-1 text-xs"
          >
            <X className="h-3.5 w-3.5" />
            <span>Reject</span>
          </Button>

          <Button
            variant="success"
            size="sm"
            disabled={isSubmitting}
            onClick={() => handleAction("APPROVED")}
            className="gap-1 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            <Check className="h-3.5 w-3.5" />
            <span>Approve & Resume</span>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
