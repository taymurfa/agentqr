"use client";

import { ChatMessage } from "@/types";
import { X, FileText, TrendingUp, BarChart3 } from "lucide-react";

interface ResearchPanelProps {
  messages: ChatMessage[];
  onClose: () => void;
}

export function ResearchPanel({ messages, onClose }: ResearchPanelProps) {
  const agentMessages = messages.filter(
    (m) => m.role === "assistant" && m.agents_used && m.agents_used.length > 0
  );

  const sourceTypes = new Map<string, number>();
  agentMessages.forEach((msg) => {
    msg.context_sources?.forEach((src) => {
      const type = src.type || "unknown";
      sourceTypes.set(type, (sourceTypes.get(type) || 0) + 1);
    });
  });

  return (
    <div className="w-80 shrink-0 overflow-y-auto rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border p-3">
        <h3 className="text-sm font-semibold">Research Context</h3>
        <button onClick={onClose} className="rounded p-1 hover:bg-accent">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-4 p-3">
        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground uppercase">Agents Used</h4>
          <div className="space-y-1">
            {Array.from(
              new Set(agentMessages.flatMap((m) => m.agents_used || []))
            ).map((agent) => (
              <div key={agent} className="flex items-center gap-2 text-sm">
                {agent === "sector_researcher" && <FileText className="h-3 w-3" />}
                {agent === "technical_analyst" && <TrendingUp className="h-3 w-3" />}
                {agent === "fundamental_analyst" && <BarChart3 className="h-3 w-3" />}
                <span>{agent.replace(/_/g, " ")}</span>
              </div>
            ))}
            {agentMessages.length === 0 && (
              <p className="text-xs text-muted-foreground">No agents invoked yet</p>
            )}
          </div>
        </div>

        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground uppercase">Data Sources</h4>
          <div className="space-y-1">
            {sourceTypes.size > 0 ? (
              Array.from(sourceTypes.entries()).map(([type, count]) => (
                <div key={type} className="flex items-center justify-between text-sm">
                  <span>{type.replace(/_/g, " ")}</span>
                  <span className="text-xs text-muted-foreground">{count} refs</span>
                </div>
              ))
            ) : (
              <p className="text-xs text-muted-foreground">Ask a question to see sources</p>
            )}
          </div>
        </div>

        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground uppercase">Quick Commands</h4>
          <div className="space-y-1 text-xs text-muted-foreground">
            <p><code>/research TICKER</code> — Full research</p>
            <p><code>/compare A,B,C</code> — Compare</p>
            <p><code>/technical TICKER</code> — Technicals</p>
            <p><code>/fundamental TICKER</code> — Fundamentals</p>
            <p><code>/strategy SECTOR</code> — Strategy</p>
          </div>
        </div>
      </div>
    </div>
  );
}
