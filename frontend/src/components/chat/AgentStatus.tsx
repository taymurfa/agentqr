"use client";

import { AgentStatus } from "@/types";
import { cn } from "@/lib/utils";
import { Brain, TrendingUp, FileText, BarChart3, Loader2, CheckCircle } from "lucide-react";

const agentIcons: Record<string, React.ElementType> = {
  orchestrator: Brain,
  sector_researcher: FileText,
  technical_analyst: TrendingUp,
  fundamental_analyst: BarChart3,
};

const agentLabels: Record<string, string> = {
  orchestrator: "Orchestrator",
  sector_researcher: "Sector Researcher",
  technical_analyst: "Technical Analyst",
  fundamental_analyst: "Fundamental Analyst",
};

interface AgentStatusBarProps {
  status: AgentStatus;
}

export function AgentStatusBar({ status }: AgentStatusBarProps) {
  const Icon = agentIcons[status.agent] || Brain;
  const label = agentLabels[status.agent] || status.agent;
  const isWorking = status.status === "thinking" || status.status === "working";

  return (
    <div className="flex items-center gap-2 border-b border-border bg-muted/50 px-4 py-2">
      <Icon className={cn("h-4 w-4", isWorking ? "text-yellow-500" : "text-green-500")} />
      <span className="text-xs font-medium">{label}</span>
      {isWorking ? (
        <Loader2 className="h-3 w-3 animate-spin text-yellow-500" />
      ) : (
        <CheckCircle className="h-3 w-3 text-green-500" />
      )}
      <span className="text-xs text-muted-foreground">{status.status}</span>
    </div>
  );
}
