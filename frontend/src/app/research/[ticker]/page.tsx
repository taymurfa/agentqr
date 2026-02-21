"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { companiesApi, researchApi } from "@/lib/api";
import { formatNumber, formatPercent } from "@/lib/utils";
import {
  Loader2,
  RefreshCw,
  ArrowLeft,
  TrendingUp,
  BarChart3,
  Shield,
  DollarSign,
  Activity,
  Building2,
  FileText,
  Brain,
  LineChart,
  BookOpen,
  Globe,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ─── Markdown renderer with consistent table/prose styles ───────────────────
function MdContent({ content }: { content: string }) {
  return (
    <div
      className="
        prose prose-sm dark:prose-invert max-w-none
        prose-headings:font-semibold prose-headings:text-foreground
        prose-h2:text-base prose-h3:text-sm
        prose-p:text-muted-foreground prose-p:leading-relaxed
        prose-li:text-muted-foreground
        prose-strong:text-foreground prose-strong:font-semibold
        prose-code:text-primary prose-code:bg-muted/60 prose-code:rounded prose-code:px-1
        prose-table:w-full prose-table:border-collapse
        prose-th:border prose-th:border-border prose-th:bg-muted/30 prose-th:p-2 prose-th:text-left prose-th:text-xs prose-th:font-semibold prose-th:text-foreground
        prose-td:border prose-td:border-border prose-td:p-2 prose-td:text-xs prose-td:text-muted-foreground
        prose-hr:border-border
        [&_table]:rounded-lg [&_table]:overflow-hidden
      "
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

// ─── Agent tab config ─────────────────────────────────────────────────────────
const AGENT_CONFIG: Record<
  string,
  { label: string; icon: React.ElementType; color: string; bg: string; border: string }
> = {
  sector_researcher: {
    label: "Sector Researcher",
    icon: Globe,
    color: "text-violet-400",
    bg: "bg-violet-500/10",
    border: "border-violet-500/30",
  },
  technical_analyst: {
    label: "Technical Analyst",
    icon: LineChart,
    color: "text-blue-400",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  fundamental_analyst: {
    label: "Fundamental Analyst",
    icon: BookOpen,
    color: "text-amber-400",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
  orchestrator: {
    label: "Orchestrator",
    icon: Brain,
    color: "text-emerald-400",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
};

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function CompanyDetailPage() {
  const params = useParams();
  const ticker = (params.ticker as string)?.toUpperCase();
  const [company, setCompany] = useState<Record<string, unknown> | null>(null);
  const [researchResult, setResearchResult] = useState<Record<string, unknown> | null>(null);
  const [researching, setResearching] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);

  useEffect(() => {
    if (ticker) loadCompany();
  }, [ticker]);

  async function loadCompany() {
    setLoading(true);
    try {
      const data = await companiesApi.get(ticker);
      setCompany(data);
    } catch {
      setCompany(null);
    }
    setLoading(false);
  }

  async function runResearch() {
    setResearching(true);
    setResearchResult(null);
    setActiveAgent(null);
    try {
      const result = await researchApi.run(ticker);
      setResearchResult(result);
      // Select first agent tab by default
      const agents = (result.agents_used as string[]) || [];
      if (agents.length > 0) setActiveAgent(agents[0]);
      await loadCompany();
    } catch (e) {
      console.error(e);
      setResearchResult({ error: "Research failed. Check backend logs for details." });
    }
    setResearching(false);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  if (!company || company.error) {
    return (
      <div className="py-12 text-center">
        <h2 className="text-xl font-bold">Company Not Found</h2>
        <p className="mt-2 text-muted-foreground">{ticker} has not been ingested yet.</p>
        <Link href="/research" className="mt-4 inline-flex items-center gap-1 text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back to Research
        </Link>
      </div>
    );
  }

  const fundamentals = (company.fundamentals as Record<string, number | null>) || {};
  const hasStoredSummary = !!company.research_summary;
  const agentResults = (researchResult?.agent_results as Record<string, unknown>[]) || [];
  const agentsUsed = (researchResult?.agents_used as string[]) || [];

  const getAgentResult = (name: string) =>
    agentResults.find((r) => r.agent === name);

  return (
    <div className="space-y-6">
      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-start gap-4">
        <Link href="/research" className="mt-1 rounded-lg p-2 hover:bg-accent">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold tracking-tight">
            {(company.name as string) || ticker}
            <span className="ml-2 text-lg font-normal text-muted-foreground">({ticker})</span>
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <Building2 className="h-3.5 w-3.5" />
            <span>{company.sector as string}</span>
            {company.industry && (
              <>
                <span className="text-muted-foreground/40">·</span>
                <span>{company.industry as string}</span>
              </>
            )}
          </div>
        </div>
        <button
          onClick={runResearch}
          disabled={researching}
          className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 px-5 py-2.5 text-sm font-medium text-white shadow-lg shadow-blue-500/20 transition-all hover:shadow-xl hover:opacity-90 disabled:opacity-50"
        >
          {researching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          {researching ? "Researching..." : "Run Research"}
        </button>
      </div>

      {/* ── Key Metrics ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          { label: "Market Cap", value: company.market_cap ? formatNumber(company.market_cap as number) : "N/A", icon: DollarSign, color: "text-emerald-500" },
          { label: "P/E Ratio", value: fundamentals.pe_ratio?.toFixed(2) ?? "N/A", icon: BarChart3, color: "text-blue-500" },
          { label: "Profit Margin", value: fundamentals.profit_margin != null ? formatPercent(fundamentals.profit_margin) : "N/A", icon: TrendingUp, color: "text-violet-500" },
          { label: "Revenue Growth", value: fundamentals.revenue_growth != null ? formatPercent(fundamentals.revenue_growth) : "N/A", icon: Activity, color: "text-amber-500" },
          { label: "Debt/Equity", value: fundamentals.debt_to_equity?.toFixed(2) ?? "N/A", icon: Shield, color: "text-red-500" },
          { label: "ROE", value: fundamentals.roe != null ? formatPercent(fundamentals.roe) : "N/A", icon: FileText, color: "text-cyan-500" },
        ].map((m) => (
          <div key={m.label} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-1.5">
              <m.icon className={`h-3.5 w-3.5 ${m.color}`} />
              <p className="text-xs text-muted-foreground">{m.label}</p>
            </div>
            <p className="mt-1.5 text-lg font-bold">{m.value}</p>
          </div>
        ))}
      </div>

      {/* ── Financial Ratios ───────────────────────────────────────────── */}
      {Object.keys(fundamentals).length > 0 && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="mb-4 flex items-center gap-2 text-base font-semibold">
            <BarChart3 className="h-4 w-4 text-blue-500" />
            Financial Ratios
          </h2>
          <div className="grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-3 lg:grid-cols-4">
            {Object.entries(fundamentals)
              .filter(([, v]) => v != null)
              .map(([key, value]) => (
                <div key={key} className="flex items-center justify-between border-b border-border/40 pb-2">
                  <span className="text-sm text-muted-foreground">
                    {key.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" ")}
                  </span>
                  <span className="text-sm font-semibold">
                    {typeof value === "number"
                      ? Math.abs(value) < 1 ? formatPercent(value) : value.toFixed(2)
                      : String(value)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* ── Research In Progress ───────────────────────────────────────── */}
      {researching && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/5 px-6 py-8">
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="relative">
              <div className="h-12 w-12 rounded-full border-2 border-blue-500/30" />
              <Loader2 className="absolute inset-1.5 h-9 w-9 animate-spin text-blue-500" />
            </div>
            <div>
              <h3 className="font-semibold text-blue-400">Multi-Agent Research Running</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Sector Researcher · Fundamental Analyst · Technical Analyst are working in sequence.
                <br />
                This typically takes 45–90 seconds.
              </p>
            </div>
            <div className="flex gap-3">
              {["Sector Researcher", "Fundamental Analyst", "Technical Analyst"].map((a) => (
                <span key={a} className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs text-blue-400">
                  {a}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Live Research Result ───────────────────────────────────────── */}
      {researchResult && !researchResult.error && (
        <div className="space-y-4">
          {/* Completion banner */}
          <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-5 py-3">
            <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-500" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-emerald-400">Research Complete</p>
              <p className="text-xs text-muted-foreground">
                {agentsUsed.filter(a => !(agentResults.find(r => r.agent === a)?.error)).length} of {agentsUsed.length} agents succeeded · {new Date().toLocaleTimeString()}
              </p>
            </div>
            <div className="flex gap-2">
              {agentsUsed.map((agent) => {
                const cfg = AGENT_CONFIG[agent];
                const agentResult = agentResults.find(r => r.agent === agent);
                const hasError = !!agentResult?.error;
                if (!cfg) return null;
                const Icon = hasError ? AlertTriangle : cfg.icon;
                return (
                  <span key={agent} className={`flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${hasError ? "bg-orange-500/10 text-orange-400" : `${cfg.bg} ${cfg.color}`
                    }`}>
                    <Icon className="h-3 w-3" /> {cfg.label}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Orchestrator synthesis — full width card */}
          <div className="rounded-xl border border-emerald-500/20 bg-card">
            <div className="flex items-center gap-3 border-b border-border px-6 py-4">
              <Brain className="h-5 w-5 text-emerald-400" />
              <div>
                <h2 className="font-semibold">Orchestrator Synthesis</h2>
                <p className="text-xs text-muted-foreground">Unified recommendation from all agents</p>
              </div>
            </div>
            <div className="px-6 py-5">
              <MdContent content={(researchResult.synthesis as string) || ""} />
            </div>
          </div>

          {/* Agent detail tabs */}
          {agentsUsed.filter((a) => a !== "orchestrator").length > 0 && (
            <div className="rounded-xl border border-border bg-card">
              {/* Tab bar */}
              <div className="flex overflow-x-auto border-b border-border">
                {agentsUsed
                  .filter((a) => a !== "orchestrator")
                  .map((agent) => {
                    const cfg = AGENT_CONFIG[agent];
                    const agentResult = agentResults.find(r => r.agent === agent);
                    const hasError = !!agentResult?.error;
                    const displayCfg = cfg || {
                      label: agent.split("_").map((w: string) => w.charAt(0).toUpperCase() + w.slice(1)).join(" "),
                      icon: FileText,
                      color: "text-muted-foreground",
                      bg: "bg-muted/40",
                      border: "border-border",
                    };
                    const Icon = hasError ? AlertTriangle : displayCfg.icon;
                    const isActive = activeAgent === agent;
                    return (
                      <button
                        key={agent}
                        onClick={() => setActiveAgent(agent)}
                        className={`flex shrink-0 items-center gap-2 border-b-2 px-5 py-3.5 text-sm font-medium transition-colors ${isActive
                            ? hasError
                              ? "border-orange-400 text-orange-400"
                              : `${displayCfg.color} border-current`
                            : "border-transparent text-muted-foreground hover:text-foreground"
                          }`}
                      >
                        <Icon className="h-4 w-4" />
                        {displayCfg.label}
                        {hasError && <span className="ml-1 rounded-full bg-orange-500/20 px-1.5 py-0.5 text-xs text-orange-400">failed</span>}
                      </button>
                    );
                  })}
              </div>

              {/* Tab content */}
              {activeAgent && (() => {
                const result = getAgentResult(activeAgent);
                const cfg = AGENT_CONFIG[activeAgent];
                const hasError = !!(result as Record<string, unknown>)?.error;

                if (!result) return (
                  <div className="px-6 py-8 text-center text-sm text-muted-foreground">
                    No output from this agent.
                  </div>
                );

                return (
                  <div className="px-6 py-5">
                    {/* Agent header */}
                    {cfg && (
                      <div className={`mb-4 flex items-center gap-3 rounded-lg border px-4 py-3 ${hasError
                          ? "border-orange-500/30 bg-orange-500/10"
                          : `${cfg.bg} ${cfg.border}`
                        }`}>
                        {hasError
                          ? <AlertTriangle className="h-5 w-5 shrink-0 text-orange-400" />
                          : <cfg.icon className={`h-5 w-5 shrink-0 ${cfg.color}`} />
                        }
                        <div>
                          <p className={`text-sm font-semibold ${hasError ? "text-orange-400" : cfg.color}`}>
                            {cfg.label} {hasError ? "— Partial Failure" : "Output"}
                          </p>
                          {activeAgent === "technical_analyst" && (result as Record<string, unknown>).signal && (
                            <p className="text-xs text-muted-foreground">
                              Signal: <span className="font-medium">{((result as Record<string, unknown>).signal as Record<string, unknown>)?.signal as string || "N/A"}</span>
                              {" · "}Confidence: <span className="font-medium">{((result as Record<string, unknown>).signal as Record<string, unknown>)?.confidence as number || 0}%</span>
                            </p>
                          )}
                          {hasError && (
                            <p className="mt-0.5 text-xs text-orange-400/80">
                              Error: {(result as Record<string, unknown>).error as string}
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                    {(result.content as string) && (result.content as string) !== `Agent failed: ${(result as Record<string, unknown>).error}` ? (
                      <MdContent content={result.content as string} />
                    ) : hasError ? (
                      <div className="rounded-lg border border-orange-500/20 bg-orange-500/5 p-4 text-sm text-orange-300/80">
                        This agent encountered an error and could not produce a report. The Orchestrator Synthesis above incorporates the available data from the other agents.
                      </div>
                    ) : null}
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {/* ── Error state ────────────────────────────────────────────────── */}
      {researchResult?.error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/5 p-5">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
          <p className="text-sm text-red-400">{researchResult.error as string}</p>
        </div>
      )}

      {/* ── Stored summary (when no live result) ──────────────────────── */}
      {hasStoredSummary && !researchResult && (
        <div className="rounded-xl border border-border bg-card">
          <div className="flex items-center gap-3 border-b border-border px-6 py-4">
            <FileText className="h-5 w-5 text-violet-500" />
            <div>
              <h2 className="font-semibold">Previous Research Summary</h2>
              <p className="text-xs text-muted-foreground">From the last research run</p>
            </div>
          </div>
          <div className="px-6 py-5">
            <MdContent content={company.research_summary as string} />
          </div>
        </div>
      )}

      {/* ── Company description ────────────────────────────────────────── */}
      {!!company.description && (
        <div className="rounded-xl border border-border bg-card p-6">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            About {(company.name as string) || ticker}
          </h2>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {company.description as string}
          </p>
        </div>
      )}
    </div>
  );
}
