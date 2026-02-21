"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Slash } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const commands = [
    { cmd: "/research", desc: "Research a ticker", example: "/research AAPL" },
    { cmd: "/compare", desc: "Compare tickers", example: "/compare AAPL,GOOGL,MSFT" },
    { cmd: "/technical", desc: "Technical analysis", example: "/technical NVDA" },
    { cmd: "/fundamental", desc: "Fundamental analysis", example: "/fundamental TSLA" },
    { cmd: "/strategy", desc: "Generate strategy", example: "/strategy tech-sector" },
  ];

  useEffect(() => {
    setShowCommands(input === "/");
  }, [input]);

  const handleSubmit = () => {
    if (!input.trim() || isLoading) return;
    onSend(input.trim());
    setInput("");
    setShowCommands(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const insertCommand = (cmd: string) => {
    setInput(cmd + " ");
    setShowCommands(false);
    inputRef.current?.focus();
  };

  return (
    <div className="relative border-t border-border p-4">
      {showCommands && (
        <div className="absolute bottom-full left-4 right-4 mb-2 rounded-lg border border-border bg-card p-2 shadow-lg">
          <p className="mb-2 px-2 text-xs font-medium text-muted-foreground">COMMANDS</p>
          {commands.map((c) => (
            <button
              key={c.cmd}
              onClick={() => insertCommand(c.cmd)}
              className="flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
            >
              <Slash className="h-3 w-3 text-muted-foreground" />
              <span className="font-medium">{c.cmd}</span>
              <span className="text-muted-foreground">{c.desc}</span>
              <span className="ml-auto text-xs text-muted-foreground">{c.example}</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2 rounded-xl border border-border bg-background p-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about a company, sector, or strategy... (type / for commands)"
          className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground"
          rows={1}
          disabled={isLoading}
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          className="rounded-lg bg-primary p-2 text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
