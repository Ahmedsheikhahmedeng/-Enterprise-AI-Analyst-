"use client";

import React from "react";
import { Citation } from "@/types/platform";
import { CitationBadge } from "@/features/evidence/citation-badge";

interface MarkdownRendererProps {
  content: string;
  citations?: Citation[];
  onCitationClick?: (citationId: string) => void;
  isStreaming?: boolean;
}

export function MarkdownRenderer({
  content,
  citations = [],
  onCitationClick,
  isStreaming = false,
}: MarkdownRendererProps) {
  if (!content) {
    return isStreaming ? <span className="streaming-cursor" /> : null;
  }

  // Regex to match citation tags like [S1], [D2], [G1], [M3]
  const citationRegex = /(\[[A-Z]\d+\])/g;

  // Split into paragraphs / lines
  const paragraphs = content.split("\n\n");

  const renderInlineContent = (text: string) => {
    const parts = text.split(citationRegex);
    return parts.map((part, index) => {
      const match = part.match(/^\[([A-Z]\d+)\]$/);
      if (match) {
        const citationId = part; // e.g. "[S1]"
        const citationData = citations.find((c) => c.citation_id === citationId);
        return (
          <CitationBadge
            key={index}
            citationId={citationId}
            citation={citationData}
            onClick={() => onCitationClick?.(citationId)}
          />
        );
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="prose prose-sm dark:prose-invert max-w-none space-y-3 leading-relaxed text-foreground">
      {paragraphs.map((p, pIdx) => {
        const trimmed = p.trim();
        if (!trimmed) return null;

        // Heading 3: ###
        if (trimmed.startsWith("### ")) {
          return (
            <h4 key={pIdx} className="text-sm font-semibold tracking-tight text-foreground mt-4 mb-2">
              {renderInlineContent(trimmed.replace("### ", ""))}
            </h4>
          );
        }

        // Heading 2: ##
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={pIdx} className="text-base font-bold tracking-tight text-foreground mt-5 mb-2 border-b border-border/40 pb-1">
              {renderInlineContent(trimmed.replace("## ", ""))}
            </h3>
          );
        }

        // Heading 1: #
        if (trimmed.startsWith("# ")) {
          return (
            <h2 key={pIdx} className="text-lg font-extrabold tracking-tight text-foreground mt-6 mb-3">
              {renderInlineContent(trimmed.replace("# ", ""))}
            </h2>
          );
        }

        // Bullet list: - or *
        if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
          const items = trimmed.split("\n").filter((l) => l.trim().length > 0);
          return (
            <ul key={pIdx} className="list-disc list-inside space-y-1 my-2 text-sm text-foreground/90 pl-2">
              {items.map((item, iIdx) => (
                <li key={iIdx}>
                  {renderInlineContent(item.replace(/^[-*]\s+/, ""))}
                </li>
              ))}
            </ul>
          );
        }

        // Table detection: begins with |
        if (trimmed.startsWith("|") && trimmed.includes("\n|")) {
          const rows = trimmed.split("\n").filter((r) => r.trim().startsWith("|"));
          if (rows.length >= 2) {
            const headerCells = rows[0]
              .split("|")
              .map((c) => c.trim())
              .filter((c) => c.length > 0);
            const dataRows = rows.slice(2).map((r) =>
              r
                .split("|")
                .map((c) => c.trim())
                .filter((c) => c.length > 0)
            );

            return (
              <div key={pIdx} className="my-4 overflow-x-auto rounded-lg border border-border/80 bg-card">
                <table className="w-full text-left text-xs">
                  <thead className="bg-muted/60 border-b border-border/80">
                    <tr>
                      {headerCells.map((h, hIdx) => (
                        <th key={hIdx} className="px-3.5 py-2 font-semibold text-foreground">
                          {renderInlineContent(h)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/60">
                    {dataRows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-muted/30 transition-colors">
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} className="px-3.5 py-2 text-foreground/90 font-mono text-[11px]">
                            {renderInlineContent(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          }
        }

        // Code block: ```
        if (trimmed.startsWith("```")) {
          const lines = trimmed.split("\n");
          const lang = lines[0].replace("```", "").trim() || "text";
          const code = lines.slice(1, -1).join("\n");
          return (
            <div key={pIdx} className="my-3 overflow-hidden rounded-lg border border-border bg-muted/40">
              <div className="flex items-center justify-between px-3 py-1.5 bg-muted/80 border-b border-border/60 text-[11px] font-mono text-muted-foreground">
                <span>{lang}</span>
              </div>
              <pre className="p-3 text-xs font-mono overflow-x-auto text-foreground">
                <code>{code}</code>
              </pre>
            </div>
          );
        }

        // Standard paragraph
        return (
          <p key={pIdx} className="text-sm leading-relaxed text-foreground/90">
            {renderInlineContent(trimmed)}
          </p>
        );
      })}
      {isStreaming && <span className="streaming-cursor" />}
    </div>
  );
}
