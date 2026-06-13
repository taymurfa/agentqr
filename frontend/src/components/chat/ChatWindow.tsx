"use client";

import { useEffect, useRef } from "react";
import { ChatMessage } from "@/types";
import { MessageBubble } from "./MessageBubble";

interface ChatWindowProps {
  messages: ChatMessage[];
  streamingContent: string;
  isLoading: boolean;
}

const EXAMPLES = [
  "Research AAPL — full analysis",
  "Compare NVDA, AMD, INTC",
  "/technical TSLA",
  "/strategy technology sector",
];

export function ChatWindow({ messages, streamingContent, isLoading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-5 p-6">
        <div className="text-center">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Strategy Assistant
          </p>
          <p className="mt-2 font-mono text-xs text-foreground">
            Describe what you want to research, backtest, or build.
          </p>
        </div>
        <div className="flex w-full max-w-sm flex-col gap-1">
          {EXAMPLES.map((example) => (
            <div
              key={example}
              className="cursor-pointer rounded border border-border bg-background px-2.5 py-1.5 font-mono text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {example}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto p-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}

      {streamingContent && (
        <MessageBubble
          message={{
            id: "streaming",
            role: "assistant",
            content: streamingContent,
            created_at: new Date().toISOString(),
          }}
        />
      )}

      {isLoading && !streamingContent && (
        <div className="flex items-center gap-2 px-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          <span className="flex h-1.5 w-1.5 animate-pulse rounded-full bg-foreground" />
          agents working…
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
