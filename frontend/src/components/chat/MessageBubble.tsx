"use client";

import { ChatMessage } from "@/types";
import { cn } from "@/lib/utils";
import { User, Bot } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3", isUser && "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div
        className={cn(
          "max-w-[90%] overflow-x-auto rounded-2xl px-5 py-4",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted/50 border border-border/50"
        )}
      >
        {isUser ? (
          <p className="text-sm">{message.content}</p>
        ) : (
          <div className="prose prose-sm prose-slate dark:prose-invert max-w-none 
                          prose-th:border prose-th:border-border prose-th:bg-muted/50 prose-th:p-2 
                          prose-td:border prose-td:border-border prose-td:p-2 
                          prose-table:border-collapse prose-table:w-full">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.agents_used && message.agents_used.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {message.agents_used.map((agent) => (
              <span
                key={agent}
                className="inline-flex items-center rounded-full bg-background/50 px-2 py-0.5 text-xs"
              >
                {agent.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
