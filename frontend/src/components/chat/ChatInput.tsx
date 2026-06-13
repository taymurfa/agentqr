"use client";

import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

const COMMANDS = [
  { cmd: "/research", desc: "Research a ticker", example: "/research AAPL" },
  { cmd: "/compare", desc: "Compare tickers", example: "/compare AAPL,GOOGL,MSFT" },
  { cmd: "/technical", desc: "Technical analysis", example: "/technical NVDA" },
  { cmd: "/fundamental", desc: "Fundamental analysis", example: "/fundamental TSLA" },
  { cmd: "/strategy", desc: "Generate strategy", example: "/strategy tech-sector" },
];

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [showCommands, setShowCommands] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
    <div className="relative border-t border-border p-3">
      {showCommands && (
        <div className="absolute bottom-full left-3 right-3 mb-2 rounded border border-border bg-card shadow-lg">
          <p className="border-b border-border px-3 py-1.5 font-mono text-[9px] font-semibold uppercase tracking-widest text-muted-foreground">
            Commands
          </p>
          {COMMANDS.map((c) => (
            <button
              key={c.cmd}
              onClick={() => insertCommand(c.cmd)}
              className="flex w-full items-center gap-3 border-b border-border/70 px-3 py-1.5 text-left font-mono text-[11px] transition-colors hover:bg-accent/60 last:border-b-0"
            >
              <span className="font-semibold text-foreground">{c.cmd}</span>
              <span className="text-muted-foreground">{c.desc}</span>
              <span className="ml-auto text-[10px] text-muted-foreground">{c.example}</span>
            </button>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2 rounded border border-border bg-background p-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask the agent — type / for commands"
          className="max-h-32 min-h-[28px] flex-1 resize-none bg-transparent px-1 py-0.5 font-mono text-xs text-foreground outline-none placeholder:text-muted-foreground"
          rows={1}
          disabled={isLoading}
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim() || isLoading}
          className="flex items-center gap-1 rounded border border-border bg-background px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-40 disabled:hover:bg-background disabled:hover:text-muted-foreground"
        >
          Send <Send className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}
