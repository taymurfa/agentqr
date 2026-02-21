"use client";

import { Sun, Moon, Bell, Github } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { usePathname } from "next/navigation";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/chat": "Research Chat",
  "/research": "Company Research",
  "/strategies": "Trading Strategies",
  "/monitoring": "Agent Monitoring",
};

export function Header() {
  const { theme, toggleTheme } = useTheme();
  const pathname = usePathname();
  const title = pageTitles[pathname || "/"] || "Agentic Quant Researcher";

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-card px-6">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
      </div>
      <div className="flex items-center gap-2">
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          title="GitHub Repository"
        >
          <Github className="h-4 w-4" />
        </a>
        <button
          onClick={toggleTheme}
          className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          title="Toggle theme"
        >
          {theme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>
        <button className="relative rounded-lg p-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-card" />
        </button>
      </div>
    </header>
  );
}
