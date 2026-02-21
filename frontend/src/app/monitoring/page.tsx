"use client";

import { useState, useEffect } from "react";
import { monitoringApi } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import {
  Activity,
  Brain,
  FileText,
  TrendingUp,
  BarChart3,
  Database,
  Loader2,
  RefreshCw,
  Zap,
  Clock,
  Hash,
} from "lucide-react";

const AGENT_ICONS: Record<string, typeof Brain> = {
  orchestrator: Brain,
  sector_researcher: FileText,
  technical_analyst: TrendingUp,
  fundamental_analyst: BarChart3,
  ingestion: Database,
};

const AGENT_COLORS: Record<string, string> = {
  orchestrator: "text-amber-500",
  sector_researcher: "text-blue-500",
  technical_analyst: "text-violet-500",
  fundamental_analyst: "text-emerald-500",
  ingestion: "text-cyan-500",
};

const STATUS_COLORS: Record<string, string> = {
  started: "bg-blue-500/20 text-blue-400",
  running: "bg-amber-500/20 text-amber-400",
  completed: "bg-emerald-500/20 text-emerald-400",
  failed: "bg-red-500/20 text-red-400",
};

export default function MonitoringPage() {
  const [data, setData] = useState<Awaited<
    ReturnType<typeof monitoringApi.getOverview>
  > | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const res = await monitoringApi.getOverview();
      setData(res);
    } catch {
      setData(null);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000); // Auto-refresh every 10s
    return () => clearInterval(interval);
  }, []);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  const agentStats = data?.agent_stats ?? {};
  const recentActivity = data?.recent_activity ?? [];
  const system = data?.system ?? {
    companies_ingested: 0,
    strategies_generated: 0,
    total_tokens_used: 0,
    total_agent_calls: 0,
  };

  const agentNames = [
    "orchestrator",
    "sector_researcher",
    "technical_analyst",
    "fundamental_analyst",
    "ingestion",
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agent Monitoring</h1>
          <p className="text-sm text-muted-foreground">
            Real-time agent activity, performance metrics, and system health
          </p>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* System Overview */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          {
            icon: Database,
            label: "Companies Ingested",
            value: system.companies_ingested,
            color: "text-blue-500",
          },
          {
            icon: TrendingUp,
            label: "Strategies Generated",
            value: system.strategies_generated,
            color: "text-emerald-500",
          },
          {
            icon: Zap,
            label: "Total Agent Calls",
            value: system.total_agent_calls,
            color: "text-amber-500",
          },
          {
            icon: Hash,
            label: "Tokens Used",
            value: system.total_tokens_used.toLocaleString(),
            color: "text-violet-500",
          },
        ].map((m) => (
          <div
            key={m.label}
            className="rounded-xl border border-border bg-card p-4"
          >
            <div className="flex items-center gap-2">
              <m.icon className={`h-4 w-4 ${m.color}`} />
              <span className="text-xs text-muted-foreground">{m.label}</span>
            </div>
            <p className="mt-2 text-2xl font-bold">{m.value}</p>
          </div>
        ))}
      </div>

      {/* Agent Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {agentNames.map((name) => {
          const stats = agentStats[name];
          const Icon = AGENT_ICONS[name] || Activity;
          const color = AGENT_COLORS[name] || "text-muted-foreground";
          const label = name
            .split("_")
            .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
            .join(" ");

          return (
            <div key={name} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-center gap-3">
                <Icon className={`h-5 w-5 ${color}`} />
                <div>
                  <p className="text-sm font-medium">{label}</p>
                  <p className="text-xs text-muted-foreground">
                    {stats ? `${stats.total_calls} calls` : "No activity"}
                  </p>
                </div>
              </div>
              {stats && (
                <div className="mt-3 space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Tokens</span>
                    <span className="font-medium">
                      {stats.total_tokens.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">Avg Latency</span>
                    <span className="font-medium">
                      {stats.avg_latency_ms > 1000
                        ? `${(stats.avg_latency_ms / 1000).toFixed(1)}s`
                        : `${stats.avg_latency_ms}ms`}
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Recent Activity */}
      <div className="rounded-xl border border-border bg-card">
        <div className="flex items-center gap-2 border-b border-border p-4">
          <Activity className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Recent Activity</h2>
        </div>
        <div className="max-h-[400px] overflow-y-auto">
          {recentActivity.length === 0 ? (
            <p className="p-6 text-center text-sm text-muted-foreground">
              No recent activity. Start by ingesting company data or running
              research.
            </p>
          ) : (
            <div className="divide-y divide-border">
              {recentActivity.map((log, i) => {
                const Icon = AGENT_ICONS[log.agent] || Activity;
                const color =
                  AGENT_COLORS[log.agent] || "text-muted-foreground";
                return (
                  <div
                    key={i}
                    className="flex items-start gap-3 px-4 py-3 text-sm"
                  >
                    <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${color}`} />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">
                          {log.agent
                            .split("_")
                            .map(
                              (w) =>
                                w.charAt(0).toUpperCase() + w.slice(1)
                            )
                            .join(" ")}
                        </span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_COLORS[log.status] || "bg-muted text-muted-foreground"
                            }`}
                        >
                          {log.status}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-muted-foreground">
                        {log.message}
                      </p>
                    </div>
                    <div className="shrink-0 text-right text-xs text-muted-foreground">
                      {log.tokens > 0 && (
                        <p>{log.tokens.toLocaleString()} tokens</p>
                      )}
                      <p>{formatDate(log.created_at)}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
