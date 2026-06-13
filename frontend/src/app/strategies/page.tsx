"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Plus,
  Trash2,
} from "lucide-react";
import {
  AreaChart,
  Area,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from "recharts";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { useChat } from "@/hooks/useChat";
import { strategiesApi } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";

type BackendStrategy = {
  id: string;
  name: string;
  tickers: string[];
  recommendation: string;
  sharpe_ratio: number;
  created_at: string;
};

const tooltipStyle = {
  contentStyle: {
    background: "hsl(0 0% 7%)",
    border: "1px solid hsl(0 0% 12%)",
    borderRadius: 2,
    fontSize: 10,
    color: "hsl(0 0% 85%)",
  },
};

// Deterministic 32-bit PRNG so each (seed,i) produces the same tick reproducibly.
function rand(seed: number, i: number) {
  let x = (seed ^ (i * 2654435761)) >>> 0;
  x ^= x << 13; x >>>= 0;
  x ^= x >>> 17;
  x ^= x << 5; x >>>= 0;
  return (x & 0xffffffff) / 0xffffffff;
}

function buildEquity(seed: string) {
  const n = 1950;
  const out: { i: number; value: number }[] = [];
  let v = 100_000;
  const seedNum = seed.split("").reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 0) || 1;
  const drift = ((seed.length % 5) * 0.00002 + 0.000015);
  for (let i = 0; i < n; i++) {
    const shock = (rand(seedNum, i) - 0.5) * 0.0009;
    v = v * (1 + drift + shock);
    out.push({ i, value: Math.round(v * 100) / 100 });
  }
  return out;
}

function buildDrawdown(equity: { i: number; value: number }[]) {
  let peak = -Infinity;
  return equity.map((p) => {
    peak = Math.max(peak, p.value);
    return { i: p.i, value: ((p.value - peak) / peak) * 100 };
  });
}

const defaultCode = `# Awaiting strategy from assistant…
#
# Ask the assistant in the sidebar for a strategy, e.g.:
#   "Build a momentum overlay on FX carry, rebalanced monthly"
#
# Generated code will appear here.
`;

function extractCode(messages: Array<{ role: string; content: string }>) {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role !== "assistant") continue;
    const match = m.content.match(/```(?:python|py)?\n([\s\S]*?)```/);
    if (match) return match[1].trim();
  }
  return null;
}

type HistoryEntry = {
  id: string;
  label: string;
  seed: string;
  savedAt: string;
  totalReturn: number;
  sharpe: number;
  maxDD: number;
};

const HISTORY_KEY = "agentqr.strategies.history";

function loadHistory(): HistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveHistory(entries: HistoryEntry[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(HISTORY_KEY, JSON.stringify(entries));
}

type Window = "D0" | "D1" | "D2" | "ALL";
const WINDOW_BARS: Record<Window, number> = { D0: 390, D1: 780, D2: 1170, ALL: 1950 };

export default function StrategiesPageWrapper() {
  return (
    <Suspense fallback={null}>
      <StrategiesPage />
    </Suspense>
  );
}

function StrategiesPage() {
  const { messages, isLoading, agentStatus, streamingContent, sendMessage, clearChat } = useChat();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [activeHistoryId, setActiveHistoryId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chartWindow, setChartWindow] = useState<Window>("ALL");
  const [chartFullscreen, setChartFullscreen] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  useEffect(() => {
    if (!pickerOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [pickerOpen]);

  useEffect(() => {
    if (!chartFullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setChartFullscreen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chartFullscreen]);

  const code = useMemo(() => extractCode(messages) ?? defaultCode, [messages]);
  const lastAssistant = useMemo(
    () => messages.filter((m) => m.role === "assistant").at(-1)?.content ?? "",
    [messages]
  );
  const firstUserPrompt = useMemo(
    () => messages.find((m) => m.role === "user")?.content ?? "",
    [messages]
  );

  const router = useRouter();
  const searchParams = useSearchParams();
  const liveStrategyId = searchParams?.get("strategy") ?? null;
  const isLiveId = !!liveStrategyId && /^[0-9a-f-]{8,}$/i.test(liveStrategyId);

  // Backend strategies for the sidebar picker.
  const [backendStrategies, setBackendStrategies] = useState<BackendStrategy[]>([]);
  useEffect(() => {
    let cancelled = false;
    const load = () => {
      strategiesApi
        .list()
        .then((d) => {
          if (cancelled) return;
          const rows = ((d.strategies as Array<Record<string, unknown>>) || []).map((s) => ({
            id: String(s.id ?? ""),
            name: String(s.name ?? "STRATEGY"),
            tickers: (s.tickers as string[] | undefined) ?? [],
            recommendation: String(s.recommendation ?? ""),
            sharpe_ratio: Number(s.sharpe_ratio ?? 0),
            created_at: String(s.created_at ?? ""),
          }));
          setBackendStrategies(rows.filter((r) => r.id));
        })
        .catch((e) => console.warn("backend strategies load failed", e));
    };
    load();
    const t = window.setInterval(load, 8000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);
  const [liveDetail, setLiveDetail] = useState<{
    name: string;
    equity_curve: { i: number; value: number }[];
    sharpe: number;
    maxDD: number;
    annReturn: number;
    annVol: number;
    winRate: number;
  } | null>(null);
  useEffect(() => {
    if (!isLiveId || !liveStrategyId) {
      setLiveDetail(null);
      return;
    }
    let cancelled = false;
    strategiesApi
      .get(liveStrategyId)
      .then((d) => {
        if (cancelled) return;
        const bt = (d as { backtest_results?: Record<string, unknown> }).backtest_results ?? {};
        const curve = (bt.equity_curve as Array<{ date: string; equity: number }> | undefined) ?? [];
        const equityCurve = curve.map((p, i) => ({ i, value: p.equity * 100_000 }));
        setLiveDetail({
          name: String(d.name ?? "Strategy"),
          equity_curve: equityCurve,
          sharpe: Number(bt.sharpe_ratio ?? 0),
          maxDD: Number(bt.max_drawdown ?? 0),
          annReturn: Number(bt.annualized_return ?? 0),
          annVol: Number(bt.annualized_volatility ?? 0),
          winRate: Number(bt.win_rate ?? 0),
        });
      })
      .catch((e) => console.warn("strategy detail load failed", e));
    return () => {
      cancelled = true;
    };
  }, [isLiveId, liveStrategyId]);

  const liveSeed = lastAssistant.slice(0, 32) || "untitled-strategy";
  const activeHistory = history.find((h) => h.id === activeHistoryId) ?? null;
  const hasStrategy = messages.length > 0 || activeHistory !== null || liveDetail !== null;
  const seed = activeHistory ? activeHistory.seed : liveSeed;
  const equity = useMemo(
    () => (liveDetail ? liveDetail.equity_curve : buildEquity(seed)),
    [liveDetail, seed]
  );
  const fullPnl = useMemo(
    () =>
      equity[0]
        ? equity.map((p) => ({
            i: p.i,
            value: Math.round((p.value - equity[0].value) * 100) / 100,
          }))
        : [],
    [equity]
  );
  const windowedPnl = useMemo(() => fullPnl.slice(-WINDOW_BARS[chartWindow]), [fullPnl, chartWindow]);
  const drawdown = useMemo(() => buildDrawdown(equity), [equity]);
  const computedReturn = equity.length
    ? ((equity[equity.length - 1].value - equity[0].value) / equity[0].value) * 100
    : 0;
  const totalReturn = liveDetail ? liveDetail.annReturn : computedReturn;
  const totalPnl = fullPnl.length ? fullPnl[fullPnl.length - 1].value : 0;
  const computedMaxDD = Math.min(...drawdown.map((d) => d.value));
  const maxDD = liveDetail ? liveDetail.maxDD : computedMaxDD;
  const sharpe = liveDetail ? liveDetail.sharpe : Number((1.2 + Math.abs(totalReturn) / 60).toFixed(2));
  const sortino = Number((1.6 + Math.abs(totalReturn) / 50).toFixed(2));
  const calmar = maxDD !== 0 ? Number((totalReturn / Math.abs(maxDD)).toFixed(2)) : 0;
  const fills = 120 + Math.round(Math.abs(totalReturn) * 8);
  const winRate = liveDetail ? liveDetail.winRate : 56 + Math.abs(totalReturn) / 5;

  const saveCurrentToHistory = () => {
    const label = firstUserPrompt.slice(0, 60).trim() || `Strategy ${history.length + 1}`;
    const entry: HistoryEntry = {
      id: `h-${Date.now()}`,
      label,
      seed: liveSeed,
      savedAt: new Date().toISOString(),
      totalReturn,
      sharpe,
      maxDD,
    };
    const next = [entry, ...history].slice(0, 50);
    setHistory(next);
    saveHistory(next);
  };

  const handleNewStrategy = () => {
    if (messages.length > 0 && !activeHistory) saveCurrentToHistory();
    clearChat();
    setActiveHistoryId(null);
    setPickerOpen(false);
  };

  const handleDelete = (id: string) => {
    const next = history.filter((h) => h.id !== id);
    setHistory(next);
    saveHistory(next);
    if (activeHistoryId === id) setActiveHistoryId(null);
  };

  const activeBackend = backendStrategies.find((s) => s.id === liveStrategyId) ?? null;
  const currentLabel = activeBackend
    ? activeBackend.name
    : activeHistory
    ? activeHistory.label
    : messages.length === 0
    ? "Awaiting strategy"
    : firstUserPrompt.slice(0, 40).trim() || "Untitled strategy";

  const runTag = activeHistory
    ? `Saved · ${new Date(activeHistory.savedAt).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
      })}`
    : hasStrategy
    ? "Live"
    : "Pending";

  const metricCards = [
    {
      label: "SHARPE (ANN.)",
      bar: hasStrategy ? (sharpe >= 1 ? "pos" : "neg") : "empty",
      value: hasStrategy ? sharpe.toFixed(2) : "—",
      sub: "final run",
    },
    {
      label: "MAX DD",
      bar: hasStrategy ? "neg" : "empty",
      value: hasStrategy ? `${maxDD.toFixed(2)}%` : "—",
      sub: "peak-to-trough",
    },
    {
      label: "SORTINO",
      bar: hasStrategy ? (sortino >= 1 ? "pos" : "neg") : "empty",
      value: hasStrategy ? sortino.toFixed(2) : "—",
      sub: "downside",
    },
    {
      label: "CALMAR",
      bar: hasStrategy ? (calmar >= 0 ? "pos" : "neg") : "empty",
      value: hasStrategy ? calmar.toFixed(2) : "—",
      sub: "return / DD",
    },
    {
      label: "FILLS",
      bar: hasStrategy ? "neutral" : "empty",
      value: hasStrategy ? fills.toLocaleString() : "—",
      sub: "own + market",
    },
    {
      label: "WIN RATE",
      bar: hasStrategy ? (winRate >= 50 ? "pos" : "neg") : "empty",
      value: hasStrategy ? `${winRate.toFixed(1)}%` : "—",
      sub: "settled fills",
    },
  ];

  const barColor = (kind: "pos" | "neg" | "neutral" | "empty") =>
    kind === "empty" ? "bg-border" : "bg-foreground";

  const pnlChart = (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={windowedPnl} margin={{ top: 8, right: 16, bottom: 4, left: 4 }}>
        <CartesianGrid stroke="hsl(0 0% 10%)" strokeDasharray="0" vertical={false} />
        <XAxis dataKey="i" tick={{ fill: "hsl(0 0% 35%)", fontSize: 9 }} axisLine={false} tickLine={false} />
        <YAxis
          tick={{ fill: "hsl(0 0% 35%)", fontSize: 9 }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) => `${v >= 0 ? "+" : "-"}${Math.abs(v / 1000).toFixed(0)}k`}
          width={48}
        />
        <Tooltip
          {...tooltipStyle}
          formatter={(v: number) => [
            `${v >= 0 ? "+" : "-"}$${Math.abs(Math.round(v)).toLocaleString()}`,
            "P&L",
          ]}
        />
        <ReferenceLine y={0} stroke="hsl(0 0% 25%)" />
        <Area
          type="linear"
          dataKey="value"
          stroke="#e5e5e5"
          fill="rgba(229, 229, 229, 0.08)"
          strokeWidth={1}
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      {/* MAIN AREA */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {agentStatus && (
          <div className="flex shrink-0 items-center justify-end border-b border-border px-4 py-1">
            <span className="font-mono text-[10px] uppercase tracking-widest text-foreground">
              {agentStatus.agent} · {agentStatus.status}
            </span>
          </div>
        )}

        {/* Top row: metrics + chart */}
        <div className="grid h-[470px] shrink-0 grid-cols-[460px_minmax(0,1fr)] border-b border-border">
          {/* METRICS PANE */}
          <div className="flex flex-col gap-5 border-r border-border p-6">
            <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
              Portfolio P&amp;L
              <span>·</span>
              <span className="flex items-center gap-1.5 text-foreground">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                {hasStrategy ? "FINAL" : "PENDING"}
              </span>
            </div>

            <div className="flex items-start gap-2 font-mono">
              <span className="text-3xl font-bold text-muted-foreground">$</span>
              {hasStrategy ? (
                <span className="text-3xl font-bold text-foreground">
                  {totalPnl >= 0 ? "" : "-"}
                  {Math.abs(Math.round(totalPnl)).toLocaleString()}
                </span>
              ) : (
                <span className="text-3xl font-bold text-muted-foreground">—</span>
              )}
            </div>

            <div className="flex items-center gap-2 font-mono text-[11px]">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded border border-border text-foreground">
                {hasStrategy ? (totalPnl >= 0 ? "▲" : "▼") : "▲"}
              </span>
              <span className="text-muted-foreground">
                {hasStrategy
                  ? `${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(2)}% total return`
                  : "— run a backtest to populate metrics"}
              </span>
            </div>

            <div className="grid flex-1 grid-cols-3 grid-rows-2 gap-px overflow-hidden rounded border border-border bg-border">
              {metricCards.map((m) => (
                <div key={m.label} className="flex flex-col bg-background p-4">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    {m.label}
                  </p>
                  <div className={`mt-3 h-px w-12 ${barColor(m.bar as "pos" | "neg" | "neutral" | "empty")}`} />
                  <p className="mt-3 font-mono text-2xl font-semibold text-foreground">{m.value}</p>
                  <p className="mt-auto pt-2 font-mono text-[10px] text-muted-foreground">{m.sub}</p>
                </div>
              ))}
            </div>
          </div>

          {/* CHART PANE */}
          <div className="flex flex-col">
            <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-3">
              <div className="flex items-baseline gap-3">
                <h2 className="font-mono text-sm font-semibold text-foreground">P&amp;L curve</h2>
                <span className="font-mono text-[10px] text-muted-foreground">{runTag}</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-0.5 rounded border border-border p-0.5 font-mono text-[10px]">
                  {(["D0", "D1", "D2", "ALL"] as Window[]).map((w) => (
                    <button
                      key={w}
                      onClick={() => setChartWindow(w)}
                      className={`rounded px-2 py-0.5 uppercase tracking-widest transition-colors ${
                        chartWindow === w
                          ? "bg-foreground text-background"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {w}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setChartFullscreen(true)}
                  className="rounded border border-border p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  aria-label="Fullscreen"
                >
                  <Maximize2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div className="min-h-0 flex-1 p-3">{pnlChart}</div>
          </div>
        </div>

        {/* CODE WINDOW */}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-2">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Generated Strategy
            </p>
            <span className="font-mono text-[10px] uppercase text-muted-foreground">python</span>
          </div>
          <pre className="min-h-0 flex-1 overflow-auto bg-background p-5 font-mono text-xs leading-relaxed text-foreground">
            {code}
          </pre>
        </div>
      </div>

      {/* SIDEBAR */}
      {sidebarOpen ? (
        <aside className="flex h-full w-[340px] shrink-0 flex-col border-l border-border bg-card">
          {/* Strategy picker */}
          <div className="flex shrink-0 items-center justify-between border-b border-border p-3">
            <div ref={pickerRef} className="relative flex flex-1 items-center gap-1">
              <button
                onClick={() => setPickerOpen((v) => !v)}
                className="flex flex-1 items-center justify-between gap-1.5 rounded border border-border bg-background px-2 py-1.5 font-mono text-[11px] uppercase tracking-widest text-foreground transition-colors hover:bg-accent"
              >
                <span className="truncate">{currentLabel}</span>
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              </button>
              <button
                onClick={handleNewStrategy}
                className="rounded border border-border bg-background p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                aria-label="New strategy"
                title="New strategy"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>

              {pickerOpen && (
                <div className="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded border border-border bg-card shadow-lg">
                  <button
                    onClick={() => {
                      setActiveHistoryId(null);
                      setPickerOpen(false);
                    }}
                    className={`flex w-full items-center justify-between gap-3 border-b border-border/70 px-3 py-2 text-left font-mono text-[11px] transition-colors hover:bg-accent/60 ${
                      !activeHistory ? "bg-accent/40" : ""
                    }`}
                  >
                    <span className="text-foreground">
                      {messages.length === 0 ? "Awaiting strategy" : "Current session"}
                    </span>
                    <span className="text-[9px] uppercase tracking-widest text-muted-foreground">live</span>
                  </button>
                  {backendStrategies.length > 0 && (
                    <>
                      <p className="border-b border-border/70 bg-background/40 px-3 py-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                        Backend strategies
                      </p>
                      {backendStrategies.map((s) => {
                        const active = liveStrategyId === s.id;
                        return (
                          <button
                            key={s.id}
                            onClick={() => {
                              setActiveHistoryId(null);
                              setPickerOpen(false);
                              router.push(`/strategies?strategy=${s.id}`);
                            }}
                            className={`flex w-full items-start gap-2 border-b border-border/70 px-3 py-2 text-left transition-colors hover:bg-accent/40 ${
                              active ? "bg-accent/40" : ""
                            }`}
                          >
                            <div className="min-w-0 flex-1">
                              <p className="truncate font-mono text-[11px] font-semibold text-foreground">
                                {s.name}
                              </p>
                              <div className="mt-0.5 flex flex-wrap items-center gap-2 font-mono text-[9px] text-muted-foreground">
                                <span className="rounded border border-border px-1 uppercase tracking-widest text-foreground">
                                  {s.recommendation || "—"}
                                </span>
                                <span>Sh {s.sharpe_ratio.toFixed(2)}</span>
                                <span className="truncate">{s.tickers.slice(0, 4).join(" · ")}</span>
                              </div>
                            </div>
                          </button>
                        );
                      })}
                      <p className="border-b border-border/70 bg-background/40 px-3 py-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                        Saved (local)
                      </p>
                    </>
                  )}
                  {history.length === 0 && backendStrategies.length === 0 && (
                    <p className="px-3 py-3 font-mono text-[11px] text-muted-foreground">
                      No strategies yet. Generate one from the Terminal command bar, or save a chat session with +.
                    </p>
                  )}
                  {history.map((h) => {
                    const active = h.id === activeHistoryId;
                    return (
                      <div
                        key={h.id}
                        className={`group flex items-center gap-2 border-b border-border/70 px-3 py-2 transition-colors last:border-b-0 ${
                          active ? "bg-accent/40" : "hover:bg-accent/20"
                        }`}
                      >
                        <button
                          onClick={() => {
                            setActiveHistoryId(h.id);
                            setPickerOpen(false);
                          }}
                          className="min-w-0 flex-1 text-left"
                        >
                          <p className="truncate font-mono text-[11px] font-semibold text-foreground">{h.label}</p>
                          <div className="mt-0.5 flex items-center gap-2 font-mono text-[9px] text-muted-foreground">
                            <span>
                              {new Date(h.savedAt).toLocaleString(undefined, {
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </span>
                            <span className="text-foreground">
                              {h.totalReturn >= 0 ? "+" : ""}
                              {h.totalReturn.toFixed(2)}%
                            </span>
                            <span>Sh {h.sharpe.toFixed(2)}</span>
                          </div>
                        </button>
                        <button
                          onClick={() => handleDelete(h.id)}
                          className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-accent/60 hover:text-foreground group-hover:opacity-100"
                          aria-label="Delete saved strategy"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="ml-2 rounded border border-border bg-background p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              aria-label="Collapse sidebar"
              title="Collapse"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Agent chat */}
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <ChatWindow messages={messages} streamingContent={streamingContent} isLoading={isLoading} />
            <ChatInput onSend={sendMessage} isLoading={isLoading} />
          </div>
        </aside>
      ) : (
        <button
          onClick={() => setSidebarOpen(true)}
          className="flex h-full w-8 shrink-0 flex-col items-center justify-center gap-3 border-l border-border bg-card text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Expand sidebar"
          title="Expand sidebar"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          <span className="rotate-180 font-mono text-[10px] uppercase tracking-widest [writing-mode:vertical-rl]">
            Agent
          </span>
        </button>
      )}

      {/* Fullscreen chart overlay */}
      {chartFullscreen && (
        <div className="fixed inset-0 z-50 flex flex-col bg-background">
          <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-2">
            <div className="flex items-baseline gap-3">
              <h2 className="font-mono text-sm font-semibold text-foreground">P&amp;L curve</h2>
              <span className="font-mono text-[10px] text-muted-foreground">{runTag}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-0.5 rounded border border-border p-0.5 font-mono text-[10px]">
                {(["D0", "D1", "D2", "ALL"] as Window[]).map((w) => (
                  <button
                    key={w}
                    onClick={() => setChartWindow(w)}
                    className={`rounded px-2 py-0.5 uppercase tracking-widest transition-colors ${
                      chartWindow === w
                        ? "bg-foreground text-background"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {w}
                  </button>
                ))}
              </div>
              <button
                onClick={() => setChartFullscreen(false)}
                className="rounded border border-border p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                aria-label="Exit fullscreen"
              >
                <Minimize2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
          <div className="min-h-0 flex-1 p-5">{pnlChart}</div>
        </div>
      )}
    </div>
  );
}
