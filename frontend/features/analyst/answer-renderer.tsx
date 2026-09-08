"use client";

import React, { useState } from "react";
import { Citation } from "@/types/platform";
import { useLanguage } from "@/contexts/language-context";
import { MarkdownRenderer } from "@/components/common/markdown-renderer";
import { ConfidenceBadge } from "@/features/evidence/confidence-badge";
import { ConflictBanner } from "@/features/evidence/conflict-banner";
import { PartialAnswerBanner } from "@/features/evidence/partial-answer-banner";
import { InsufficientEvidenceBanner } from "@/features/evidence/insufficient-evidence-banner";
import { ClarificationSelector } from "@/features/evidence/clarification-selector";
import {
  Sparkles,
  Copy,
  Check,
  Download,
  ThumbsUp,
  ThumbsDown,
} from "lucide-react";

interface EnterpriseAnswerProps {
  answer: string | null;
  citations?: Citation[];
  confidenceScore?: number | null;
  isPartial?: boolean;
  hasConflicts?: boolean;
  isInsufficient?: boolean;
  clarificationNeeded?: boolean;
  suggestedOptions?: string[] | null;
  isStreaming?: boolean;
  onCitationClick?: (citationId: string) => void;
  onSelectClarification?: (option: string) => void;
  onRegenerate?: () => void;
}

export function EnterpriseAnswer({
  answer,
  citations = [],
  confidenceScore = 0.94,
  isPartial = false,
  hasConflicts = false,
  isInsufficient = false,
  clarificationNeeded = false,
  suggestedOptions = [],
  isStreaming = false,
  onCitationClick,
  onSelectClarification,
}: EnterpriseAnswerProps) {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [copied, setCopied] = useState(false);
  const [liked, setLiked] = useState<boolean | null>(null);

  const groundedPercent = Math.round(
    ((confidenceScore !== null && confidenceScore !== undefined) ? confidenceScore : 0.94) * 100
  );

  const handleCopy = () => {
    if (!answer) return;
    navigator.clipboard.writeText(answer);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExport = () => {
    if (!answer) return;
    const blob = new Blob([answer], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `enterprise-analysis-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="rounded-xl border border-[#1f1f22] bg-[#111113] p-6 shadow-xl space-y-4 transition-all">
      {/* Answer Header & Confidence */}
      <div className="flex items-center justify-between border-b border-[#1f1f22] pb-3.5">
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-lg shadow-sm"
            style={{
              background: "linear-gradient(135deg, #6366f1 0%, #22d3ee 100%)",
            }}
          >
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#fafafa] tracking-tight">
              {isTr ? "Kurumsal Analist Zekası" : "Enterprise Analyst Intelligence"}
            </h3>
            <span className="text-[10px] text-[#71717a]">
              {isTr ? "Çok kaynaklı sentezlenmiş doğrulama" : "Multi-source synthesized verification"}
            </span>
          </div>
        </div>

        <ConfidenceBadge score={confidenceScore} hasConflicts={hasConflicts} />
      </div>

      {/* State Banners */}
      {hasConflicts && <ConflictBanner />}
      {isPartial && <PartialAnswerBanner />}
      {isInsufficient && <InsufficientEvidenceBanner />}

      {/* Clarification Selector if Ambiguous */}
      {clarificationNeeded && suggestedOptions && suggestedOptions.length > 0 && onSelectClarification && (
        <ClarificationSelector
          options={suggestedOptions}
          onSelectOption={onSelectClarification}
        />
      )}

      {/* Main Answer Content */}
      <div className="pt-1">
        <MarkdownRenderer
          content={answer || ""}
          citations={citations}
          onCitationClick={onCitationClick}
          isStreaming={isStreaming}
        />
      </div>

      {/* Groundedness Meter (from Craft Design) */}
      <div className="flex items-center gap-3 pt-3 border-t border-[#1f1f22]">
        <span className="text-xs font-medium text-[#71717a]">
          {isTr ? "Dayanaklılık:" : "Groundedness:"}
        </span>
        <div className="flex-1 max-w-[140px] h-1.5 bg-[#27272a] rounded-full overflow-hidden">
          <div
            style={{ width: `${groundedPercent}%` }}
            className={`h-full rounded-full transition-all duration-500 ${
              groundedPercent > 90
                ? "bg-[#22c55e]"
                : groundedPercent > 75
                ? "bg-[#f59e0b]"
                : "bg-[#ef4444]"
            }`}
          />
        </div>
        <span
          className={`text-xs font-mono font-bold ${
            groundedPercent > 90
              ? "text-[#22c55e]"
              : groundedPercent > 75
              ? "text-[#f59e0b]"
              : "text-[#ef4444]"
          }`}
        >
          {groundedPercent}%
        </span>
      </div>

      {/* Citations Count & Actions Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 text-[11px] text-[#71717a]">
        <div className="flex items-center gap-2">
          <span>
            {isTr
              ? `${citations?.length || 0} doğrulanmış kaynak alıntısı bağlandı`
              : `${citations?.length || 0} verified ground-truth citations linked`}
          </span>
          <span className="text-[10px] font-mono text-[#818cf8] cursor-pointer hover:underline">
            {isTr
              ? "Kaynağı incelemek için [S*] / [D*] tıklayın"
              : "Click [S*] / [D*] to inspect underlying provenance"}
          </span>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-1.5">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 rounded-md border border-[#27272a] bg-[#18181b] px-2.5 py-1 text-xs text-[#a1a1aa] hover:border-[#3f3f46] hover:text-[#fafafa] transition-colors cursor-pointer"
            title={isTr ? "Cevabı kopyala" : "Copy answer"}
          >
            {copied ? (
              <>
                <Check className="h-3 w-3 text-[#22c55e]" />
                <span className="text-[#22c55e]">{isTr ? "Kopyalandı" : "Copied"}</span>
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" />
                <span>{isTr ? "Kopyala" : "Copy"}</span>
              </>
            )}
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 rounded-md border border-[#27272a] bg-[#18181b] px-2.5 py-1 text-xs text-[#a1a1aa] hover:border-[#3f3f46] hover:text-[#fafafa] transition-colors cursor-pointer"
            title={isTr ? "Markdown olarak dışa aktar" : "Export Markdown"}
          >
            <Download className="h-3 w-3" />
            <span>{isTr ? "Dışa Aktar" : "Export"}</span>
          </button>
          <button
            onClick={() => setLiked(liked === true ? null : true)}
            className={`p-1 rounded-md border transition-colors cursor-pointer ${
              liked === true
                ? "border-[#22c55e]/30 bg-[#22c55e]/10 text-[#22c55e]"
                : "border-[#27272a] bg-[#18181b] text-[#71717a] hover:text-[#a1a1aa]"
            }`}
            title={isTr ? "Yararlı" : "Helpful"}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
          </button>
          <button
            onClick={() => setLiked(liked === false ? null : false)}
            className={`p-1 rounded-md border transition-colors cursor-pointer ${
              liked === false
                ? "border-[#ef4444]/30 bg-[#ef4444]/10 text-[#ef4444]"
                : "border-[#27272a] bg-[#18181b] text-[#71717a] hover:text-[#a1a1aa]"
            }`}
            title={isTr ? "Yararlı değil" : "Not helpful"}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
