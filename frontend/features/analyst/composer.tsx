"use client";

import React, { useState, useRef, useEffect } from "react";
import { useLanguage } from "@/contexts/language-context";
import { OrchestrationMode, ResponseStyle } from "@/types/platform";
import { Send, Square, Sparkles, Database, FileText, Share2, Layers } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface AnalystComposerProps {
  onSubmit: (params: {
    question: string;
    mode: OrchestrationMode;
    responseStyle: ResponseStyle;
    stream: boolean;
  }) => void;
  onStop?: () => void;
  isExecuting?: boolean;
}

export function AnalystComposer({
  onSubmit,
  onStop,
  isExecuting = false,
}: AnalystComposerProps) {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<OrchestrationMode>("AUTO");
  const [responseStyle, setResponseStyle] = useState<ResponseStyle>("STANDARD");
  const [stream, setStream] = useState(true);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isExecuting && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isExecuting]);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!question.trim() || isExecuting) return;
    onSubmit({
      question: question.trim(),
      mode,
      responseStyle,
      stream,
    });
    setQuestion("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const getModeIcon = (m: OrchestrationMode) => {
    switch (m) {
      case "AUTO":
        return <Sparkles className="h-3 w-3 text-primary" />;
      case "SQL":
        return <Database className="h-3 w-3 text-sky-500" />;
      case "RAG":
        return <FileText className="h-3 w-3 text-emerald-500" />;
      case "GRAPH":
        return <Share2 className="h-3 w-3 text-indigo-500" />;
      case "HYBRID":
        return <Layers className="h-3 w-3 text-amber-500" />;
    }
  };

  return (
    <div className="rounded-xl border border-border/80 bg-card/80 p-3 shadow-lg backdrop-blur-md transition-all focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/20">
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Input Textarea */}
        <div className="relative">
          <Textarea
            ref={textareaRef}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isExecuting}
            placeholder={
              isTr
                ? "Kurumsal finansallar, operasyonel metrikler veya doğrulanmış bilgi hakkında bir soru sorun..."
                : "Ask a question about corporate financials, operational metrics, or verified knowledge..."
            }
            className="min-h-[70px] resize-none border-0 bg-transparent p-1 text-sm shadow-none focus-visible:ring-0 placeholder:text-muted-foreground/70"
          />
        </div>

        {/* Toolbar & Selectors */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-border/50 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            {/* Mode Selector */}
            <div className="flex items-center gap-1 bg-muted/60 p-0.5 rounded-lg">
              {(["AUTO", "RAG", "SQL", "HYBRID", "GRAPH"] as OrchestrationMode[]).map((m) => {
                const isSelected = mode === m;
                return (
                  <button
                    key={m}
                    type="button"
                    disabled={isExecuting}
                    onClick={() => setMode(m)}
                    className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium transition-all ${
                      isSelected
                        ? "bg-background text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {getModeIcon(m)}
                    <span>{m}</span>
                  </button>
                );
              })}
            </div>

            {/* Response Style Selector */}
            <select
              value={responseStyle}
              onChange={(e) => setResponseStyle(e.target.value as ResponseStyle)}
              disabled={isExecuting}
              aria-label="Response Style"
              className="h-7 rounded-md border border-border/80 bg-muted/40 px-2 text-[11px] font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="STANDARD">{isTr ? "Standart" : "Standard"}</option>
              <option value="CONCISE">{isTr ? "Özet" : "Concise"}</option>
              <option value="DETAILED">{isTr ? "Ayrıntılı" : "Detailed"}</option>
              <option value="EXECUTIVE">{isTr ? "Yönetici Özeti" : "Executive"}</option>
            </select>

            {/* Stream Toggle */}
            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer select-none pl-1">
              <input
                type="checkbox"
                checked={stream}
                onChange={(e) => setStream(e.target.checked)}
                disabled={isExecuting}
                className="rounded border-border text-primary focus:ring-primary h-3.5 w-3.5"
              />
              <span>{isTr ? "Akış (SSE)" : "Stream (SSE)"}</span>
            </label>
          </div>

          {/* Action Buttons: Send or Stop */}
          <div className="flex items-center gap-2">
            {isExecuting ? (
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={onStop}
                className="h-8 gap-1.5 px-3 text-xs shadow-sm font-semibold"
              >
                <Square className="h-3.5 w-3.5 fill-current" />
                <span>{isTr ? "Durdur" : "Stop"}</span>
              </Button>
            ) : (
              <Button
                type="submit"
                size="sm"
                disabled={!question.trim()}
                className="h-8 gap-1.5 px-3 text-xs shadow-sm font-semibold"
              >
                <span>{isTr ? "Sor" : "Ask"}</span>
                <Send className="h-3.5 w-3.5" />
              </Button>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
