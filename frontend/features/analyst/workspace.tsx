"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  EvidenceItem,
  Citation,
  OrchestrationMode,
  ResponseStyle,
  StreamEvent,
} from "@/types/platform";
import { AnalystComposer } from "./composer";
import { ExecutionTimeline } from "./timeline";
import { ParallelBranches } from "./parallel-branches";
import { EnterpriseAnswer } from "./answer-renderer";
import { ConversationHistory, ConversationSummary } from "./conversation-history";
import { EvidencePanel } from "@/features/evidence/evidence-panel";
import { AnalystSSEClient } from "@/lib/sse/sse-client";
import { apiClient, PlatformApiError } from "@/lib/api/client";
import { Layers, ChevronRight, ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/language-context";

const INITIAL_CONVERSATIONS: ConversationSummary[] = [
  {
    id: "conv-1",
    title: "Q3 Enterprise Revenue & Operating Margins",
    updated_at: new Date(Date.now() - 3600000).toISOString(),
    status: "COMPLETED",
    pinned: true,
  },
  {
    id: "conv-2",
    title: "Customer Churn Analysis by Tier & Region",
    updated_at: new Date(Date.now() - 86400000).toISOString(),
    status: "COMPLETED",
  },
];

export function AnalystWorkspace() {
  const { lang } = useLanguage();
  const isTr = lang === "tr";
  const [conversations, setConversations] = useState<ConversationSummary[]>(INITIAL_CONVERSATIONS);
  const [activeConvId, setActiveConvId] = useState<string | null>("conv-1");

  // Execution State
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentExecutionId, setCurrentExecutionId] = useState<string | null>(null);
  const [currentMode, setCurrentMode] = useState<OrchestrationMode>("AUTO");
  const [currentStage, setCurrentStage] = useState<string>("UNDERSTANDING");
  const [completedStages, setCompletedStages] = useState<string[]>([]);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [isCompleted, setIsCompleted] = useState(true);
  const [isFailed, setIsFailed] = useState(false);

  // Answer & Evidence State
  const [answerContent, setAnswerContent] = useState<string | null>(
    "### Q3 Enterprise Financial Performance\n\nIn Q3 2026, total consolidated net revenue reached **$142.8M** [S1], representing an **18.4% year-over-year increase** compared to Q3 2025 ($120.6M) [D1].\n\n| Business Segment | Q3 Revenue | YoY Growth | Margin |\n|---|---|---|---|\n| Enterprise Cloud | $84.2M | +24.1% | 68.2% |\n| Platform API & Data | $38.5M | +16.0% | 74.5% |\n| Professional Services | $20.1M | +2.8% | 32.1% |\n\nOperating income expanded to **$34.6M** [S2], driven primarily by efficiency gains in infrastructure routing and automated RAG caching."
  );
  const [evidenceList, setEvidenceList] = useState<EvidenceItem[]>([
    {
      id: "S1",
      source_type: "SQL_RECORD",
      title: "financial_ledger_q3_2026.revenue",
      snippet: "SELECT SUM(net_revenue) FROM enterprise_ledgers WHERE fiscal_year = 2026 AND quarter = 'Q3' -> 142,800,000.00 USD",
      score: 0.99,
      trust_level: "DIRECT_DB",
    },
    {
      id: "S2",
      source_type: "SQL_RECORD",
      title: "operating_expenses_q3_summary",
      snippet: "SELECT operating_income FROM quarterly_financial_statements WHERE quarter = '2026-Q3' -> 34,600,000.00 USD",
      score: 0.98,
      trust_level: "DIRECT_DB",
    },
    {
      id: "D1",
      source_type: "VECTOR_CHUNK",
      title: "Q3_2025_Shareholder_Letter.pdf (p. 4)",
      snippet: "Consolidated quarterly net revenue for the third quarter ending September 30, 2025 was recorded at $120.6 million.",
      score: 0.94,
      trust_level: "VERIFIED_DOC",
    },
  ]);

  const [citationsList, setCitationsList] = useState<Citation[]>([
    {
      citation_id: "[S1]",
      source_type: "SQL_RECORD",
      title: "financial_ledger_q3_2026.revenue",
      snippet: "SELECT SUM(net_revenue) FROM enterprise_ledgers WHERE fiscal_year = 2026 AND quarter = 'Q3' -> 142,800,000.00 USD",
      trust_level: "DIRECT_DB",
      confidence: 0.99,
    },
    {
      citation_id: "[S2]",
      source_type: "SQL_RECORD",
      title: "operating_expenses_q3_summary",
      snippet: "SELECT operating_income FROM quarterly_financial_statements WHERE quarter = '2026-Q3' -> 34,600,000.00 USD",
      trust_level: "DIRECT_DB",
      confidence: 0.98,
    },
    {
      citation_id: "[D1]",
      source_type: "VECTOR_CHUNK",
      title: "Q3_2025_Shareholder_Letter.pdf",
      snippet: "Consolidated quarterly net revenue for the third quarter ending September 30, 2025 was recorded at $120.6 million.",
      trust_level: "VERIFIED_DOC",
      confidence: 0.94,
    },
  ]);

  const [confidenceScore, setConfidenceScore] = useState<number | null>(0.96);
  const [hasConflicts, setHasConflicts] = useState(false);
  const [isPartial, setIsPartial] = useState(false);
  const [isInsufficient, setIsInsufficient] = useState(false);
  const [clarificationNeeded, setClarificationNeeded] = useState(false);
  const [suggestedOptions, setSuggestedOptions] = useState<string[] | null>(null);

  // UI Panels
  const [showEvidencePanel, setShowEvidencePanel] = useState(false);
  const [showHistorySidebar, setShowHistorySidebar] = useState(true);
  const [highlightedCitationId, setHighlightedCitationId] = useState<string | null>(null);

  // SSE client reference
  const sseClientRef = useRef<AnalystSSEClient | null>(null);

  const handleCitationClick = useCallback((citationId: string) => {
    setHighlightedCitationId(citationId);
    setShowEvidencePanel(true);
  }, []);

  const handleNewChat = () => {
    const newId = `conv-${Date.now()}`;
    const newConv: ConversationSummary = {
      id: newId,
      title: "New Analysis",
      updated_at: new Date().toISOString(),
      status: "COMPLETED",
    };
    setConversations([newConv, ...conversations]);
    setActiveConvId(newId);
    setAnswerContent(null);
    setEvidenceList([]);
    setCitationsList([]);
    setProgressPercent(0);
    setIsCompleted(false);
    setIsFailed(false);
  };

  const handleStop = async () => {
    if (!currentExecutionId) return;
    try {
      if (sseClientRef.current) {
        sseClientRef.current.disconnect();
      }
      await apiClient.ask.cancel(currentExecutionId);
      setIsExecuting(false);
      setIsFailed(true);
      setAnswerContent((prev) => (prev ? `${prev}\n\n*[Execution cancelled by user]*` : "*[Execution cancelled]*"));
    } catch (err) {
      console.error("Failed to cancel execution:", err);
    }
  };

  const handleAskSubmit = async ({
    question,
    mode,
    responseStyle,
    stream,
  }: {
    question: string;
    mode: OrchestrationMode;
    responseStyle: ResponseStyle;
    stream: boolean;
  }) => {
    setIsExecuting(true);
    setIsCompleted(false);
    setIsFailed(false);
    setCurrentMode(mode);
    setCurrentStage("UNDERSTANDING");
    setCompletedStages([]);
    setProgressPercent(5);
    setAnswerContent("");
    setEvidenceList([]);
    setCitationsList([]);
    setHasConflicts(false);
    setIsPartial(false);
    setIsInsufficient(false);
    setClarificationNeeded(false);

    // Update conversation title if new
    if (activeConvId) {
      setConversations((prev) =>
        prev.map((c) =>
          c.id === activeConvId
            ? { ...c, title: question.slice(0, 42) + (question.length > 42 ? "..." : "") }
            : c
        )
      );
    }

    try {
      const response = await apiClient.ask.submit({
        question,
        mode,
        response_style: responseStyle,
        stream,
        conversation_id: activeConvId,
      });

      const payload = response.data;
      if (!payload) throw new Error("Missing response payload");

      setCurrentExecutionId(payload.execution_id);
      setIsPartial(payload.is_partial || false);
      setHasConflicts(payload.has_conflicts || false);
      setClarificationNeeded(payload.clarification_needed || false);
      setSuggestedOptions(payload.suggested_options || null);

      // If synchronous response
      if (!stream || payload.status === "COMPLETED") {
        setAnswerContent(payload.answer);
        setEvidenceList(payload.evidence || []);
        setCitationsList(payload.citations || []);
        setConfidenceScore(payload.confidence_score ?? 0.95);
        setProgressPercent(100);
        setIsCompleted(true);
        setIsExecuting(false);
        return;
      }

      // If streaming, connect via AnalystSSEClient
      if (stream) {
        if (sseClientRef.current) {
          sseClientRef.current.disconnect();
        }

        const sseClient = new AnalystSSEClient({
          executionId: payload.execution_id,
          onEvent: (event: StreamEvent) => {
            handleSSEEvent(event);
          },
          onError: (err: Error) => {
            console.warn("SSE connection error:", err);
          },
        });

        sseClientRef.current = sseClient;
        sseClient.connect();
      }
    } catch (err) {
      setIsExecuting(false);
      setIsFailed(true);
      const message = err instanceof PlatformApiError ? err.message : "Execution failed";
      setAnswerContent(`**Error**: ${message}`);
    }
  };

  const handleSSEEvent = (event: StreamEvent) => {
    const { event: eventType, data } = event;

    switch (eventType) {
      case "execution_started":
        setProgressPercent(10);
        break;

      case "execution_stage":
      case "execution_progress": {
        const stage = (data.stage as string) || "PLANNING";
        const progress = typeof data.progress === "number" ? data.progress : null;
        setCurrentStage(stage);
        setCompletedStages((prev) => (prev.includes(stage) ? prev : [...prev, stage]));
        if (progress != null) setProgressPercent(progress);
        break;
      }

      case "evidence_collected": {
        const items = (data.evidence as EvidenceItem[]) || [];
        setEvidenceList((prev) => [...prev, ...items]);
        break;
      }

      case "response_chunk": {
        const chunk = (data.chunk as string) || "";
        setAnswerContent((prev) => (prev || "") + chunk);
        break;
      }

      case "response_completed": {
        const finalAnswer = data.answer as string | undefined;
        if (finalAnswer) setAnswerContent(finalAnswer);
        const finalCitations = data.citations as Citation[] | undefined;
        if (finalCitations) setCitationsList(finalCitations);
        const score = typeof data.confidence_score === "number" ? data.confidence_score : 0.95;
        setConfidenceScore(score);
        setProgressPercent(100);
        setIsCompleted(true);
        setIsExecuting(false);
        break;
      }

      case "execution_failed": {
        setIsFailed(true);
        setIsExecuting(false);
        const errorMsg = (data.error as string) || "Execution encountered an error";
        setAnswerContent((prev) => `${prev || ""}\n\n**Error**: ${errorMsg}`);
        break;
      }

      case "execution_cancelled": {
        setIsFailed(true);
        setIsExecuting(false);
        setAnswerContent((prev) => `${prev || ""}\n\n*[Execution cancelled]*`);
        break;
      }
    }
  };

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (sseClientRef.current) {
        sseClientRef.current.disconnect();
      }
    };
  }, []);

  return (
    <div className="flex h-[calc(100vh-3.5rem)] w-full overflow-hidden bg-background">
      {/* Left: Conversation History */}
      {showHistorySidebar && (
        <div className="w-64 shrink-0 hidden lg:block">
          <ConversationHistory
            conversations={conversations}
            activeId={activeConvId}
            onSelect={(id) => setActiveConvId(id)}
            onNewChat={handleNewChat}
          />
        </div>
      )}

      {/* Center: Main Analyst Workspace */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Workspace Toolbar */}
        <div className="flex items-center justify-between border-b border-border/80 px-4 py-2 text-xs bg-card/20">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setShowHistorySidebar(!showHistorySidebar)}
              className="h-7 w-7 text-muted-foreground hidden lg:flex"
              title={isTr ? "Kenar çubuğunu aç/kapat" : "Toggle sidebar"}
            >
              {showHistorySidebar ? <ChevronLeft className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            </Button>
            <span className="font-semibold text-foreground">
              {isTr ? "Çalışma Alanı Analizi" : "Workspace Analysis"}
            </span>
            <span className="text-muted-foreground">• {isTr ? "Mod" : "Mode"}: {currentMode}</span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowEvidencePanel(!showEvidencePanel)}
            className="h-7 gap-1.5 text-xs"
          >
            <Layers className="h-3.5 w-3.5 text-primary" />
            <span>
              {isTr ? "Kanıtlar" : "Evidence"} ({evidenceList.length})
            </span>
          </Button>
        </div>

        {/* Workspace Body: Answers, Timeline, Composer */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 max-w-5xl mx-auto w-full">
          {/* Execution Timeline (when running or in progress) */}
          {(isExecuting || progressPercent > 0) && (
            <ExecutionTimeline
              currentStage={currentStage}
              completedStages={completedStages}
              progressPercent={progressPercent}
              isCompleted={isCompleted}
              isFailed={isFailed}
            />
          )}

          {/* Concurrent Hybrid Branches when in HYBRID mode */}
          {currentMode === "HYBRID" && (isExecuting || isCompleted) && (
            <ParallelBranches />
          )}

          {/* Enterprise Answer Display */}
          {(answerContent || isExecuting) && (
            <EnterpriseAnswer
              answer={answerContent}
              citations={citationsList}
              confidenceScore={confidenceScore}
              isPartial={isPartial}
              hasConflicts={hasConflicts}
              isInsufficient={isInsufficient}
              clarificationNeeded={clarificationNeeded}
              suggestedOptions={suggestedOptions}
              isStreaming={isExecuting}
              onCitationClick={handleCitationClick}
              onSelectClarification={(opt) =>
                handleAskSubmit({
                  question: opt,
                  mode: currentMode,
                  responseStyle: "STANDARD",
                  stream: true,
                })
              }
            />
          )}
        </div>

        {/* Bottom Question Composer */}
        <div className="p-4 border-t border-border/80 bg-background/90 backdrop-blur-md max-w-5xl mx-auto w-full">
          <AnalystComposer
            onSubmit={handleAskSubmit}
            onStop={handleStop}
            isExecuting={isExecuting}
          />
        </div>
      </div>

      {/* Right: Collapsible Evidence Panel */}
      {showEvidencePanel && (
        <div className="w-80 shrink-0 shadow-xl z-20">
          <EvidencePanel
            evidence={evidenceList}
            highlightedCitationId={highlightedCitationId}
            onClose={() => setShowEvidencePanel(false)}
          />
        </div>
      )}
    </div>
  );
}
