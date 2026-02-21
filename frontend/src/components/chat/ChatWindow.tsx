"use client";

import { useEffect, useRef } from "react";
import { ChatMessage } from "@/types";
import { MessageBubble } from "./MessageBubble";
import { Bot, Loader2 } from "lucide-react";

interface ChatWindowProps {
  messages: ChatMessage[];
  streamingContent: string;
  isLoading: boolean;
}

export function ChatWindow({ messages, streamingContent, isLoading }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 text-center">
        <Bot className="h-16 w-16 text-muted-foreground/40" />
        <div>
          <h2 className="text-xl font-semibold">Start a Research Conversation</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Ask about any company, sector, or trading strategy
          </p>
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {[
            "Research AAPL — full analysis",
            "Compare NVDA, AMD, INTC",
            "/technical TSLA",
            "/strategy technology sector",
          ].map((example) => (
            <div
              key={example}
              className="cursor-pointer rounded-lg border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
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
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm">Agents are researching...</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
