"use client";

import { ChatMessage } from "@/types";
import { agentTag } from "@/lib/agents";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const time = message.created_at
    ? new Date(message.created_at).toLocaleTimeString(undefined, {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-border bg-background font-mono text-[9px] font-semibold uppercase tracking-widest text-foreground">
        {isUser ? "YOU" : "AGT"}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          <span className="text-foreground">{isUser ? "you" : "agent"}</span>
          {time && <span>{time}</span>}
          {!isUser &&
            message.agents_used?.map((a) => (
              <span
                key={a}
                className="rounded border border-border px-1 text-[9px] text-muted-foreground"
              >
                {agentTag(a)}
              </span>
            ))}
        </div>

        <div className="mt-1 font-mono text-xs leading-relaxed text-foreground">
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div
              className="prose prose-invert max-w-none
                         prose-p:my-1.5 prose-p:text-xs prose-p:leading-relaxed
                         prose-headings:font-semibold prose-headings:uppercase prose-headings:tracking-widest prose-headings:text-foreground
                         prose-h1:text-[11px] prose-h2:text-[11px] prose-h3:text-[10px]
                         prose-strong:text-foreground
                         prose-a:text-foreground prose-a:underline
                         prose-code:rounded prose-code:border prose-code:border-border prose-code:bg-card prose-code:px-1 prose-code:py-0.5 prose-code:text-[11px] prose-code:font-normal prose-code:before:content-none prose-code:after:content-none
                         prose-pre:my-2 prose-pre:rounded prose-pre:border prose-pre:border-border prose-pre:bg-card prose-pre:p-3 prose-pre:text-[11px]
                         prose-ul:my-1.5 prose-ul:pl-4 prose-li:my-0.5 prose-li:text-xs
                         prose-ol:my-1.5 prose-ol:pl-4
                         prose-table:my-2 prose-table:border-collapse prose-table:text-[11px]
                         prose-th:border prose-th:border-border prose-th:bg-card prose-th:px-2 prose-th:py-1 prose-th:text-left prose-th:font-semibold prose-th:uppercase prose-th:tracking-widest
                         prose-td:border prose-td:border-border prose-td:px-2 prose-td:py-1
                         prose-hr:my-3 prose-hr:border-border"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
