"use client";

import React, { useState } from "react";
import { MessageSquare, Pin, Search, Plus, Clock } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import { useLanguage } from "@/contexts/language-context";

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
  status: "COMPLETED" | "RUNNING" | "FAILED";
  pinned?: boolean;
}

interface ConversationHistoryProps {
  conversations: ConversationSummary[];
  activeId?: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
}

export function ConversationHistory({
  conversations,
  activeId,
  onSelect,
  onNewChat,
}: ConversationHistoryProps) {
  const [search, setSearch] = useState("");
  const { lang } = useLanguage();
  const isTr = lang === "tr";

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  const pinned = filtered.filter((c) => c.pinned);
  const recent = filtered.filter((c) => !c.pinned);

  return (
    <div className="flex h-full flex-col border-r border-border bg-card/40 backdrop-blur-xs">
      {/* New Chat Header */}
      <div className="p-3 border-b border-border/80">
        <Button
          size="sm"
          onClick={onNewChat}
          className="w-full justify-start gap-2 h-9 text-xs font-semibold shadow-xs"
        >
          <Plus className="h-4 w-4" />
          <span>{isTr ? "Yeni Analiz" : "New Analysis"}</span>
        </Button>
      </div>

      {/* Search Input */}
      <div className="p-2.5 border-b border-border/60">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={isTr ? "Geçmişte ara..." : "Search history..."}
            className="h-8 pl-8 text-xs bg-background/60"
          />
        </div>
      </div>

      {/* History Lists */}
      <div className="flex-1 overflow-y-auto p-2 space-y-4">
        {/* Pinned Section */}
        {pinned.length > 0 && (
          <div className="space-y-1">
            <div className="flex items-center gap-1.5 px-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
              <Pin className="h-3 w-3" />
              <span>{isTr ? "Sabitlenenler" : "Pinned"}</span>
            </div>
            {pinned.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelect(item.id)}
                className={`flex w-full flex-col items-start rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                  activeId === item.id
                    ? "bg-primary text-primary-foreground font-medium shadow-xs"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                <div className="flex w-full items-center justify-between gap-1">
                  <span className="truncate font-medium">{item.title}</span>
                  <Pin className="h-2.5 w-2.5 shrink-0 opacity-60" />
                </div>
                <span className="text-[10px] opacity-70 mt-0.5">
                  {formatDate(item.updated_at)}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* Recent Section */}
        <div className="space-y-1">
          <div className="flex items-center gap-1.5 px-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>{isTr ? "Son Analizler" : "Recent"}</span>
          </div>
          {recent.length === 0 ? (
            <div className="p-4 text-center text-xs text-muted-foreground">
              {isTr ? "Kayıtlı analiz bulunamadı." : "No conversations found."}
            </div>
          ) : (
            recent.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelect(item.id)}
                className={`flex w-full flex-col items-start rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                  activeId === item.id
                    ? "bg-primary text-primary-foreground font-medium shadow-xs"
                    : "text-foreground hover:bg-muted"
                }`}
              >
                <div className="flex w-full items-center gap-2">
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
                  <span className="truncate font-medium flex-1">{item.title}</span>
                </div>
                <div className="flex w-full items-center justify-between text-[10px] opacity-70 mt-1 pl-5">
                  <span>{formatDate(item.updated_at)}</span>
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      item.status === "COMPLETED"
                        ? "bg-emerald-500"
                        : item.status === "RUNNING"
                        ? "bg-primary animate-pulse"
                        : "bg-destructive"
                    }`}
                  />
                </div>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
