"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  BookOpen,
  ChevronDown,
  ChevronRight,
  CircleDot,
  ExternalLink,
  FileText,
  Newspaper,
  ShieldAlert,
} from "lucide-react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { agentTag } from "@/lib/agents";
import { CandlestickChart } from "@/components/terminal/CandlestickChart";
import {
  marketApi,
  monitoringApi,
  strategiesApi,
  tradingApi,
  type AgentEvent,
  type MonitoringOverview,
  type TradingAccount,
  type TradingOrder,
  type TradingPosition,
} from "@/lib/api";

const watchlist = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD"];

type StrategyStatus =
  | "RUNNING"
  | "PAPER"
  | "RESEARCHING"
  | "BACKTESTING"
  | "RISK"
  | "PAUSED";

type Strategy = {
  id: string;
  name: string;
  sector: string;
  ticker: string;
  status: StrategyStatus;
  dayPct: number;
  weekPct: number;
  mtdPct: number;
  ytdPct: number;
  sharpe: number;
  maxDD: number;
  allocationPct: number;
  params: { label: string; value: string }[];
  spark: number[];
  riskNote?: string;
};

const strategies: Strategy[] = [
  {
    id: "mom-carry-fx",
    name: "MOM-CARRY-FX",
    sector: "FX",
    ticker: "AAPL",
    status: "RUNNING",
    dayPct: 0.42,
    weekPct: 1.84,
    mtdPct: 4.1,
    ytdPct: 18.3,
    sharpe: 2.14,
    maxDD: -8.7,
    allocationPct: 28,
    params: [
      { label: "Universe", value: "G10 FX · 14 crosses" },
      { label: "Signal", value: "Momentum 63d × inverse-vol" },
      { label: "Rebalance", value: "Weekly · 1.5bps cost" },
      { label: "Max position", value: "12% NAV" },
    ],
    spark: [1, 1.01, 1.03, 1.02, 1.04, 1.06, 1.05, 1.07, 1.06, 1.075, 1.08, 1.084],
  },
  {
    id: "basis-crypto",
    name: "BASIS-CRYPTO",
    sector: "CRYPTO",
    ticker: "AMD",
    status: "RUNNING",
    dayPct: 0.31,
    weekPct: 2.14,
    mtdPct: 5.6,
    ytdPct: 21.4,
    sharpe: 2.42,
    maxDD: -6.1,
    allocationPct: 14,
    params: [
      { label: "Venue", value: "Binance · Deribit" },
      { label: "Signal", value: "Funding > 3bps daily" },
      { label: "Rebalance", value: "Daily roll" },
      { label: "Max position", value: "8% NAV" },
    ],
    spark: [1, 1.02, 1.01, 1.04, 1.06, 1.05, 1.07, 1.08, 1.09, 1.1, 1.11, 1.121],
  },
  {
    id: "vol-harvest",
    name: "VOLT-HARVEST",
    sector: "VOL",
    ticker: "NVDA",
    status: "PAPER",
    dayPct: -0.08,
    weekPct: 0.42,
    mtdPct: 0.9,
    ytdPct: 6.7,
    sharpe: 1.12,
    maxDD: -3.4,
    allocationPct: 0,
    params: [
      { label: "Universe", value: "SPX · NDX index options" },
      { label: "Signal", value: "VRP > 1σ, skew < 6" },
      { label: "Rebalance", value: "2× weekly" },
      { label: "Max position", value: "5% NAV (paper)" },
    ],
    spark: [1, 1.01, 1.005, 1.012, 1.008, 1.011, 1.013, 1.012, 1.009, 1.011, 1.014, 1.011],
  },
  {
    id: "regime-rn",
    name: "REGIME-RN +4",
    sector: "MULTI",
    ticker: "GOOGL",
    status: "BACKTESTING",
    dayPct: 0,
    weekPct: 0,
    mtdPct: 0,
    ytdPct: 8.1,
    sharpe: 1.74,
    maxDD: -5.2,
    allocationPct: 0,
    params: [
      { label: "Gates", value: "4 new regime classifiers" },
      { label: "Signal", value: "Stack router (RN-style)" },
      { label: "Rebalance", value: "Daily" },
      { label: "Max position", value: "Pending review" },
    ],
    spark: [1, 1.01, 1.02, 1.03, 1.04, 1.03, 1.05, 1.06, 1.07, 1.075, 1.08, 1.081],
  },
  {
    id: "stat-arb",
    name: "STAT-ARB-7",
    sector: "EQ",
    ticker: "MSFT",
    status: "RESEARCHING",
    dayPct: 0,
    weekPct: 0,
    mtdPct: 0,
    ytdPct: 4.2,
    sharpe: 0.96,
    maxDD: -2.1,
    allocationPct: 0,
    params: [
      { label: "Universe", value: "Top 50 US equities" },
      { label: "Signal", value: "Pairs cointegration · 90d" },
      { label: "Rebalance", value: "Intraday (15m)" },
      { label: "Max position", value: "Pending universe swap" },
    ],
    spark: [1, 1, 1.001, 1, 1.002, 1.001, 1.003, 1.002, 1.004, 1.003, 1.005, 1.004],
  },
  {
    id: "gamma-scalp",
    name: "GAMMA-SCALP",
    sector: "VOL",
    ticker: "TSLA",
    status: "RISK",
    dayPct: -0.62,
    weekPct: -1.4,
    mtdPct: -1.8,
    ytdPct: -0.6,
    sharpe: 0.18,
    maxDD: -7.9,
    allocationPct: 6,
    params: [
      { label: "Universe", value: "TSLA · MEGA-cap single names" },
      { label: "Signal", value: "Short-dated gamma scalp" },
      { label: "Rebalance", value: "Intraday" },
      { label: "Max position", value: "Capped to 3% NAV" },
    ],
    spark: [1, 1.01, 1.005, 1.008, 1.003, 0.998, 0.995, 0.99, 0.993, 0.991, 0.988, 0.986],
    riskNote: "VaR breach 2.3σ — auto-paused, awaiting approval",
  },
];

const STATUS_LABEL: Record<StrategyStatus, string> = {
  RUNNING: "Running",
  PAPER: "Paper",
  RESEARCHING: "Researching",
  BACKTESTING: "Backtesting",
  RISK: "Risk Flagged",
  PAUSED: "Paused",
};

type ReviewItem = {
  id: string;
  kind: "promotion" | "param" | "guardrail";
  strategy: string;
  message: string;
};

const reviewQueue: ReviewItem[] = [
  { id: "rv-1", kind: "promotion", strategy: "BASIS-CRYPTO", message: "Ready to promote from paper → live (8% allocation)." },
  { id: "rv-2", kind: "param", strategy: "MOM-CARRY-FX", message: "Agent proposes lookback 63 → 84 (Sharpe +0.18)." },
  { id: "rv-3", kind: "guardrail", strategy: "GAMMA-SCALP", message: "Auto-pause triggered — confirm or override." },
];

type MarketAlert = {
  id: string;
  source: string;
  message: string;
  impacts: string[];
};

type ReadingItem = {
  id: string;
  kind: "NEWS" | "PAPER" | "NOTE";
  source: string;
  title: string;
  summary: string;
  why: string;
  url: string;
};

const readingByStrategy: Record<string, ReadingItem[]> = {
  "mom-carry-fx": [
    {
      id: "mc-1",
      kind: "PAPER",
      source: "SSRN · 2024",
      title: "Carry, Momentum, and Global Imbalances in FX",
      summary: "Cross-sectional momentum overlay on G10 carry improves Sharpe by 0.4 vs. carry-only baseline.",
      why: "Direct analogue to your MOM-CARRY-FX construction — re-validates the 63d lookback the agent is proposing.",
      url: "https://papers.ssrn.com/sol3/results.cfm?txtKey_Words=fx+carry+momentum",
    },
    {
      id: "mc-2",
      kind: "NEWS",
      source: "Reuters",
      title: "USDJPY tests 156, MoF reiterates intervention readiness",
      summary: "Intra-day vol spike + tighter spreads in Tokyo session; carry leg most exposed to a JPY rally.",
      why: "MOM-CARRY-FX is long carry, short funders — a JPY squeeze hits the biggest single book.",
      url: "https://www.reuters.com/markets/currencies/",
    },
    {
      id: "mc-3",
      kind: "NOTE",
      source: "BIS Quarterly",
      title: "FX volatility regime shifts and carry drawdowns",
      summary: "VIX-FX > 12 historically precedes 80% of carry-strategy drawdowns within 4 weeks.",
      why: "Current FX vol regime score is 11.8 — close to the threshold flagged by REGIME-RN.",
      url: "https://www.bis.org/publ/qtrpdf/",
    },
  ],
  "basis-crypto": [
    {
      id: "bc-1",
      kind: "NEWS",
      source: "Coindesk",
      title: "BTC perp basis widens to 12% as funding stays positive",
      summary: "Annualised basis at 12.4% on Binance and Deribit; spot–perp spread holds despite ETF outflows.",
      why: "Active live trade — backs the 8% allocation bump pending in Needs Review.",
      url: "https://www.coindesk.com/",
    },
    {
      id: "bc-2",
      kind: "PAPER",
      source: "arXiv · 2310",
      title: "Funding rate dynamics and cash-and-carry returns in crypto",
      summary: "Funding > 0.03% daily threshold delivers ~9% annualised after cost — matches your live realised.",
      why: "Empirical support for keeping the strategy live through funding-positive regimes.",
      url: "https://arxiv.org/abs/2310",
    },
  ],
  "vol-harvest": [
    {
      id: "vh-1",
      kind: "PAPER",
      source: "JPM 2023",
      title: "Short-vol overlays and skew-driven crashes",
      summary: "VRP harvesting works in low-skew regimes; sharp tail kicks when 1m skew steepens above 6.",
      why: "Helps frame why VOLT-HARVEST stays in paper trading until skew normalises.",
      url: "https://jpm.pm-research.com/",
    },
    {
      id: "vh-2",
      kind: "NEWS",
      source: "Bloomberg",
      title: "VIX term structure flattens ahead of CPI print",
      summary: "1m–3m flat at 0.6 — historically a weak environment for short-vol carry.",
      why: "Suggests delaying VOLT-HARVEST live promotion past tomorrow's release.",
      url: "https://www.bloomberg.com/markets",
    },
  ],
  "regime-rn": [
    {
      id: "rr-1",
      kind: "PAPER",
      source: "arXiv · 2407",
      title: "Regime-aware portfolio routing with neural network gates",
      summary: "RN-style models improve risk-adjusted return by 23% vs. naive equal-weight on multi-strategy stacks.",
      why: "Methodological reference — agent is currently backtesting +4 new regimes.",
      url: "https://arxiv.org/abs/2407",
    },
  ],
  "stat-arb": [
    {
      id: "sa-1",
      kind: "NOTE",
      source: "Internal · Research Agent",
      title: "Pairs basket refresh proposal · STAT-ARB-7",
      summary: "Drop AAPL/MSFT, add NVDA/AMD; cointegration p-value 0.02 over the last 90 sessions.",
      why: "Agent is researching this swap right now — paper here outlines the rationale.",
      url: "#",
    },
    {
      id: "sa-2",
      kind: "PAPER",
      source: "SSRN · 2022",
      title: "Statistical arbitrage in semis: a sector-specific analysis",
      summary: "Cross-sectional mean reversion in semis has shrunk post-2022 but still tradeable intraday.",
      why: "Direct evidence the proposed NVDA/AMD pair is viable on shorter horizons.",
      url: "https://papers.ssrn.com/",
    },
  ],
  "gamma-scalp": [
    {
      id: "gs-1",
      kind: "NEWS",
      source: "FT",
      title: "TSLA realised vol jumps after delivery guide",
      summary: "30d realised at 64%; implied 58% — gamma scalping window opens again.",
      why: "Direct read-through for GAMMA-SCALP, currently risk-flagged on a 2.3σ VaR breach.",
      url: "https://www.ft.com/",
    },
    {
      id: "gs-2",
      kind: "PAPER",
      source: "JPM 2021",
      title: "Risk management for short-dated gamma strategies",
      summary: "Position sizing rules that historically would have avoided 8 of 10 VaR breaches.",
      why: "Templates for the guardrail-rewrite the agent is proposing.",
      url: "https://jpm.pm-research.com/",
    },
  ],
};

const marketAlerts: MarketAlert[] = [
  { id: "al-1", source: "FOMC", message: "Powell signals 25bps cut path for Q3 — dovish tilt vs. priced.", impacts: ["MOM-CARRY-FX", "REGIME-RN"] },
  { id: "al-2", source: "FX", message: "USDJPY > 156 intervention zone; vol jumping into Tokyo close.", impacts: ["MOM-CARRY-FX"] },
  { id: "al-3", source: "CRYPTO", message: "BTC perp basis widened to 12.4% annualized.", impacts: ["BASIS-CRYPTO"] },
];

const wholeMoney = (n: number) =>
  `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const signedMoney = (n: number) =>
  `${n >= 0 ? "+" : "-"}$${Math.abs(n).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const pct = (n: number, digits = 2) =>
  `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;

const SectionLabel = ({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) => (
  <div className="flex items-center justify-between">
    <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{children}</p>
    {right}
  </div>
);

function CompactTickerTape({ quotes }: { quotes: Array<{ ticker: string; price: number; changePct: number }> }) {
  if (quotes.length === 0) {
    return (
      <div className="flex h-6 items-center border-b border-border bg-card px-3 font-mono text-[10px] text-muted-foreground">
        Loading market data…
      </div>
    );
  }
  return (
    <div className="flex h-6 shrink-0 items-center gap-5 overflow-x-auto border-b border-border bg-card px-3 font-mono text-[10px]">
      {quotes.map((q) => (
        <span key={q.ticker} className="whitespace-nowrap">
          <span className="font-semibold text-foreground">{q.ticker}</span>{" "}
          <span className="text-muted-foreground">{q.price.toFixed(2)}</span>{" "}
          <span className="text-foreground">
            {q.changePct >= 0 ? "▲" : "▼"} {pct(q.changePct)}
          </span>
        </span>
      ))}
    </div>
  );
}

function StatusBadge({ status }: { status: StrategyStatus }) {
  const variant: Record<StrategyStatus, string> = {
    RUNNING: "border-foreground/40 text-foreground",
    PAPER: "border-border text-muted-foreground",
    RESEARCHING: "border-border text-muted-foreground",
    BACKTESTING: "border-border text-muted-foreground",
    RISK: "border-foreground/60 bg-foreground/5 text-foreground",
    PAUSED: "border-border text-muted-foreground",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[9px] uppercase tracking-widest ${variant[status]}`}
    >
      {status === "RISK" && <ShieldAlert className="h-2.5 w-2.5" />}
      {STATUS_LABEL[status]}
    </span>
  );
}

const Sparkline = ({ data }: { data: number[] }) => (
  <ResponsiveContainer width="100%" height="100%">
    <LineChart data={data.map((v, i) => ({ i, v }))}>
      <Line type="monotone" dataKey="v" stroke="#e5e5e5" strokeWidth={1} dot={false} isAnimationActive={false} />
    </LineChart>
  </ResponsiveContainer>
);

export default function HomePage() {
  const [selectedId, setSelectedId] = useState<string>(strategies[0].id);
  const [account, setAccount] = useState<TradingAccount | null>(null);
  const [orders, setOrders] = useState<TradingOrder[]>([]);
  const [positions, setPositions] = useState<TradingPosition[]>([]);
  const [overview, setOverview] = useState<MonitoringOverview | null>(null);
  const [quotes, setQuotes] = useState<Array<{ ticker: string; price: number; changePct: number }>>([]);
  const [blotterOpen, setBlotterOpen] = useState(false);
  const [feedFilter, setFeedFilter] = useState<"ALL" | "ALERTS" | "RESEARCH" | "RISK" | "CODE">("ALL");
  const [liveStrategies, setLiveStrategies] = useState<Strategy[]>([]);
  const [liveEvents, setLiveEvents] = useState<AgentEvent[]>([]);

  // Merge real backend strategies in front of the demo ones, deduped by id.
  const allStrategies = useMemo(() => {
    const seen = new Set<string>();
    const merged: Strategy[] = [];
    for (const s of [...liveStrategies, ...strategies]) {
      if (seen.has(s.id)) continue;
      seen.add(s.id);
      merged.push(s);
    }
    return merged;
  }, [liveStrategies]);
  const selected = allStrategies.find((s) => s.id === selectedId) ?? allStrategies[0];

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      Promise.allSettled([
        tradingApi.getAccount(),
        tradingApi.getOrders(20),
        tradingApi.getPositions(),
        monitoringApi.getOverview(),
      ]).then(([acc, ord, pos, mon]) => {
        if (cancelled) return;
        if (acc.status === "fulfilled") setAccount(acc.value);
        if (ord.status === "fulfilled") setOrders(ord.value.orders ?? []);
        if (pos.status === "fulfilled") setPositions(pos.value.positions ?? []);
        if (mon.status === "fulfilled") setOverview(mon.value);
      });
    };
    refresh();
    const t = window.setInterval(refresh, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  // Load live strategies from the backend.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await strategiesApi.list();
        if (cancelled) return;
        const mapped: Strategy[] = (data.strategies || [])
          .map((s) => mapBackendStrategy(s))
          .filter(Boolean) as Strategy[];
        setLiveStrategies(mapped);
      } catch (e) {
        console.warn("strategies load failed", e);
      }
    };
    load();
    const t = window.setInterval(load, 6000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  // Subscribe to real-time agent events via SSE (all jobs, since this page no longer submits commands).
  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const es = new EventSource(`${apiUrl}/api/agent-events/stream`);
    es.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as AgentEvent;
        setLiveEvents((prev) => {
          if (prev.some((e) => e.id === event.id)) return prev;
          return [event, ...prev].slice(0, 30);
        });
      } catch (e) {
        console.warn("bad SSE payload", e);
      }
    };
    es.onerror = () => {
      // EventSource auto-reconnects; just log.
      console.warn("SSE connection error");
    };
    return () => es.close();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const results = await Promise.allSettled(
        watchlist.map(async (ticker) => {
          const data = await marketApi.getCandles(ticker, "1d", "5m", 80);
          const first = data.candles[0];
          const latest = data.candles.at(-1);
          if (!first || !latest) return null;
          return {
            ticker,
            price: latest.close,
            changePct: ((latest.close - first.open) / first.open) * 100,
          };
        })
      );
      if (cancelled) return;
      const next: typeof quotes = [];
      for (const r of results) {
        if (r.status === "fulfilled" && r.value) next.push(r.value);
      }
      setQuotes(next);
    };
    load();
    const t = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  const equity = account?.equity ?? 24_891_406;
  const dayPnl = positions.reduce((s, p) => s + (p.unrealized_pnl ?? 0), 0) || 583_201;
  const dayPct = (dayPnl / Math.max(equity, 1)) * 100;
  const livePosition = positions.find((p) => p.ticker === selected.ticker);

  // Load real backtest detail when a live strategy is selected.
  const [liveDetail, setLiveDetail] = useState<{
    id: string;
    equity_curve?: Array<{ date: string; equity: number }>;
    signal_type?: string;
    lookback_days?: number;
    rebalance?: string;
    risk_status?: string;
    risk_flags?: string[];
    hypothesis?: string;
    universe?: string[];
    sharpe_ratio?: number;
    max_drawdown?: number;
    annualized_return?: number;
    annualized_volatility?: number;
    win_rate?: number;
  } | null>(null);
  const isLiveSelected = liveStrategies.some((s) => s.id === selected.id);
  useEffect(() => {
    if (!isLiveSelected) {
      setLiveDetail(null);
      return;
    }
    let cancelled = false;
    strategiesApi
      .get(selected.id)
      .then((d) => {
        if (cancelled) return;
        const bt = (d as { backtest_results?: Record<string, unknown> }).backtest_results ?? {};
        setLiveDetail({
          id: selected.id,
          equity_curve: bt.equity_curve as Array<{ date: string; equity: number }> | undefined,
          signal_type: bt.signal_type as string | undefined,
          lookback_days: bt.lookback_days as number | undefined,
          rebalance: bt.rebalance as string | undefined,
          risk_status: bt.risk_status as string | undefined,
          risk_flags: bt.risk_flags as string[] | undefined,
          hypothesis: (bt.hypothesis as string | undefined) ?? (d.rationale as string | undefined),
          universe: bt.universe as string[] | undefined,
          sharpe_ratio: bt.sharpe_ratio as number | undefined,
          max_drawdown: bt.max_drawdown as number | undefined,
          annualized_return: bt.annualized_return as number | undefined,
          annualized_volatility: bt.annualized_volatility as number | undefined,
          win_rate: bt.win_rate as number | undefined,
        });
      })
      .catch((e) => console.warn("strategy detail load failed", e));
    return () => {
      cancelled = true;
    };
  }, [isLiveSelected, selected.id]);

  // Filter agent feed; surface only meaningful entries (drop generic 'started' noise).
  const feed = useMemo(() => {
    const fromCommand = liveEvents.map((e) => ({
      agent: e.agent,
      status: e.status,
      message: e.message,
      tokens: 0,
      latency_ms: e.latency_ms,
      created_at: e.created_at,
    }));
    const all = [...fromCommand, ...(overview?.recent_activity ?? [])];
    return all
      .filter((e) => {
        const msg = (e.message || "").toLowerCase();
        const status = (e.status || "").toLowerCase();
        if (status === "started") return false;
        if (feedFilter === "ALL") return true;
        if (feedFilter === "ALERTS") return /alert|warn|breach|halt|trip/.test(msg) || status === "failed";
        if (feedFilter === "RESEARCH") return ["sector_researcher", "fundamental_analyst", "technical_analyst"].includes(e.agent);
        if (feedFilter === "RISK") return /risk|drawdown|var|exposure|stop/.test(msg);
        if (feedFilter === "CODE") return /code|backtest|strategy|signal/.test(msg);
        return true;
      })
      .slice(0, 12);
  }, [overview, feedFilter, liveEvents]);

  const filledOrders = orders.filter(
    (o) => o.status?.toUpperCase() === "FILLED" || o.status?.toUpperCase() === "WORKING"
  );

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-background">
      <CompactTickerTape quotes={quotes} />

      <div className="grid min-h-0 flex-1 grid-cols-[300px_minmax(0,1fr)_340px] overflow-hidden">
        {/* LEFT */}
        <aside className="flex min-w-0 flex-col gap-3 overflow-y-auto border-r border-border bg-card p-3">
          {/* Portfolio summary */}
          <section className="rounded border border-border p-3">
            <SectionLabel>Portfolio</SectionLabel>
            <p className="mt-2 font-mono text-xl font-bold text-foreground">{wholeMoney(equity)}</p>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">NAV</p>
            <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5 font-mono text-[11px]">
              <Field label="Day P&L" value={`${dayPnl >= 0 ? "▲" : "▼"} ${signedMoney(dayPnl)}`} />
              <Field label="Day %" value={pct(dayPct)} />
              <Field label="Sharpe" value="1.84" />
              <Field label="Max DD" value="-12.4%" />
            </div>
          </section>

          {/* Allocation */}
          <section className="rounded border border-border">
            <div className="border-b border-border p-3 pb-2">
              <SectionLabel
                right={
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {strategies.filter((s) => s.allocationPct > 0).length} live
                  </span>
                }
              >
                Allocation
              </SectionLabel>
            </div>
            <ul>
              {strategies
                .slice()
                .filter((s) => s.allocationPct > 0)
                .sort((a, b) => b.allocationPct - a.allocationPct)
                .map((s) => {
                  const w = Math.min(100, s.allocationPct);
                  return (
                    <li key={s.id} className="border-b border-border/70 px-3 py-2 last:border-b-0">
                      <div className="flex items-baseline justify-between font-mono text-[11px]">
                        <span className="truncate font-semibold text-foreground">{s.name}</span>
                        <span className="text-foreground">{s.allocationPct.toFixed(0)}%</span>
                      </div>
                      <div className="mt-1.5 h-1 w-full rounded bg-border">
                        <div className="h-full rounded bg-foreground/80" style={{ width: `${w}%` }} />
                      </div>
                    </li>
                  );
                })}
              <li className="flex items-baseline justify-between border-t border-border/70 px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                <span>Cash / reserve</span>
                <span className="text-foreground">
                  {Math.max(
                    0,
                    100 - strategies.reduce((sum, s) => sum + s.allocationPct, 0)
                  ).toFixed(0)}
                  %
                </span>
              </li>
            </ul>
          </section>

          {/* Needs review */}
          <section className="rounded border border-border">
            <div className="border-b border-border p-3 pb-2">
              <SectionLabel right={<span className="font-mono text-[10px] text-foreground">{reviewQueue.length}</span>}>
                Needs Review
              </SectionLabel>
            </div>
            <ul>
              {reviewQueue.map((r) => (
                <li key={r.id} className="border-b border-border/70 px-3 py-2 last:border-b-0">
                  <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    <CircleDot className="h-2.5 w-2.5" />
                    {r.strategy}
                  </div>
                  <p className="mt-1 font-mono text-[11px] text-foreground">{r.message}</p>
                  <div className="mt-2 flex gap-2 font-mono text-[10px]">
                    <button className="rounded border border-foreground/50 px-2 py-0.5 uppercase tracking-widest text-foreground transition-colors hover:bg-foreground hover:text-background">
                      Approve
                    </button>
                    <button className="rounded border border-border px-2 py-0.5 uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground">
                      Dismiss
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>
        </aside>

        {/* CENTER */}
        <main className="flex min-w-0 flex-col overflow-y-auto p-3">

          {/* Selected strategy snapshot */}
          <section className="mt-3 rounded border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <div className="flex items-center gap-2">
                <StrategyPicker
                  strategies={allStrategies}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                />
                <StatusBadge status={selected.status} />
                <span className="font-mono text-[10px] text-muted-foreground">
                  · {selected.ticker} · {selected.sector}
                </span>
              </div>
              <Link
                href={`/strategies?strategy=${selected.id}`}
                className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground hover:text-foreground"
              >
                Open <ChevronRight className="h-3 w-3" />
              </Link>
            </div>

            <div className="grid grid-cols-4 gap-3 border-b border-border px-3 py-2">
              {liveDetail ? (
                <>
                  <Metric label="Ann. Return" value={pct(liveDetail.annualized_return ?? 0)} />
                  <Metric label="Sharpe" value={(liveDetail.sharpe_ratio ?? 0).toFixed(2)} />
                  <Metric label="Max DD" value={pct(liveDetail.max_drawdown ?? 0)} />
                  <Metric label="Win Rate" value={`${(liveDetail.win_rate ?? 0).toFixed(0)}%`} />
                </>
              ) : (
                <>
                  <Metric label="1D" value={pct(selected.dayPct)} />
                  <Metric label="1W" value={pct(selected.weekPct)} />
                  <Metric label="MTD" value={pct(selected.mtdPct)} />
                  <Metric label="YTD" value={pct(selected.ytdPct)} />
                </>
              )}
            </div>

            <div className="h-[300px]">
              {liveDetail?.equity_curve && liveDetail.equity_curve.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={liveDetail.equity_curve}
                    margin={{ top: 8, right: 12, bottom: 4, left: 4 }}
                  >
                    <CartesianGrid stroke="hsl(0 0% 12%)" strokeDasharray="0" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: "hsl(0 0% 35%)", fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      minTickGap={60}
                    />
                    <YAxis
                      tick={{ fill: "hsl(0 0% 35%)", fontSize: 9 }}
                      axisLine={false}
                      tickLine={false}
                      width={42}
                      domain={["auto", "auto"]}
                      tickFormatter={(v: number) => v.toFixed(2)}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "hsl(0 0% 7%)",
                        border: "1px solid hsl(0 0% 12%)",
                        borderRadius: 2,
                        fontSize: 10,
                        color: "hsl(0 0% 85%)",
                      }}
                      formatter={(v: number) => [v.toFixed(3), "Equity (norm.)"]}
                    />
                    <Line
                      type="monotone"
                      dataKey="equity"
                      stroke="#e5e5e5"
                      strokeWidth={1.25}
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <CandlestickChart ticker={selected.ticker} />
              )}
            </div>

            {selected.riskNote && (
              <div className="flex items-center gap-2 border-t border-border px-3 py-2 font-mono text-[11px] text-foreground">
                <AlertTriangle className="h-3.5 w-3.5" />
                Risk: {selected.riskNote}
              </div>
            )}
          </section>

          {/* Agent-suggested reading */}
          <section className="mt-3 rounded border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <SectionLabel
                right={
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    curated by agent for {selected.name}
                  </span>
                }
              >
                Suggested Reading
              </SectionLabel>
            </div>
            <ul>
              {(readingByStrategy[selected.id] ?? []).map((r) => (
                <li key={r.id} className="border-b border-border/70 px-3 py-2 last:border-b-0">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 shrink-0 text-muted-foreground">
                      {r.kind === "NEWS" ? (
                        <Newspaper className="h-3.5 w-3.5" />
                      ) : r.kind === "PAPER" ? (
                        <BookOpen className="h-3.5 w-3.5" />
                      ) : (
                        <FileText className="h-3.5 w-3.5" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                        <span className="rounded border border-border px-1 text-foreground">{r.kind}</span>
                        <span>{r.source}</span>
                      </div>
                      <a
                        href={r.url}
                        target={r.url.startsWith("http") ? "_blank" : undefined}
                        rel={r.url.startsWith("http") ? "noopener noreferrer" : undefined}
                        className="mt-1 flex items-baseline gap-1 font-mono text-[12px] font-semibold text-foreground hover:underline"
                      >
                        {r.title}
                        {r.url.startsWith("http") && (
                          <ExternalLink className="h-3 w-3 text-muted-foreground" />
                        )}
                      </a>
                      <p className="mt-0.5 font-mono text-[11px] text-foreground/80">{r.summary}</p>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        <span className="text-foreground">Why:</span> {r.why}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
              {(readingByStrategy[selected.id] ?? []).length === 0 && (
                <li className="px-3 py-3 font-mono text-[11px] text-muted-foreground">
                  No suggested reading yet. The research agent will surface items once it has analysed this strategy.
                </li>
              )}
            </ul>
          </section>

          {/* Collapsible blotter — only if any orders exist */}
          {filledOrders.length > 0 && (
            <section className="mt-3 rounded border border-border bg-card">
              <button
                onClick={() => setBlotterOpen((v) => !v)}
                className="flex w-full items-center justify-between px-3 py-2"
              >
                <SectionLabel right={<span className="font-mono text-[10px] text-muted-foreground">{filledOrders.length}</span>}>
                  Execution Blotter
                </SectionLabel>
                <ChevronRight className={`h-3 w-3 text-muted-foreground transition-transform ${blotterOpen ? "rotate-90" : ""}`} />
              </button>
              {blotterOpen && (
                <div className="overflow-x-auto border-t border-border">
                  <table className="w-full font-mono text-[11px]">
                    <thead className="text-[9px] uppercase text-muted-foreground">
                      <tr className="border-b border-border">
                        <th className="px-3 py-1.5 text-left font-medium">Ticker</th>
                        <th className="px-2 py-1.5 text-left font-medium">Side</th>
                        <th className="px-2 py-1.5 text-right font-medium">Qty</th>
                        <th className="px-2 py-1.5 text-right font-medium">Price</th>
                        <th className="px-2 py-1.5 text-right font-medium">Status</th>
                        <th className="px-3 py-1.5 text-right font-medium">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filledOrders.slice(0, 8).map((o) => (
                        <tr key={o.id} className="border-b border-border/70">
                          <td className="px-3 py-1.5 font-semibold text-foreground">{o.ticker}</td>
                          <td className="px-2 py-1.5">
                            <span className="inline-block rounded border border-border px-1.5 text-[9px] uppercase tracking-widest text-foreground">
                              {o.side}
                            </span>
                          </td>
                          <td className="px-2 py-1.5 text-right text-foreground">{o.qty}</td>
                          <td className="px-2 py-1.5 text-right text-foreground">{o.avg_fill_price != null ? o.avg_fill_price.toFixed(2) : "—"}</td>
                          <td className="px-2 py-1.5 text-right uppercase text-muted-foreground">{o.status}</td>
                          <td className="px-3 py-1.5 text-right text-muted-foreground">{o.created_at ? new Date(o.created_at).toLocaleTimeString() : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </main>

        {/* RIGHT */}
        <aside className="flex min-w-0 flex-col gap-3 overflow-y-auto border-l border-border bg-card p-3">
          {/* Agent feed with filters */}
          <section className="flex min-h-0 flex-col rounded border border-border">
            <div className="border-b border-border p-3 pb-2">
              <SectionLabel
                right={
                  <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                    <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                    live
                  </span>
                }
              >
                Agent Activity
              </SectionLabel>
              <div className="mt-2 flex gap-1 font-mono text-[9px]">
                {(["ALL", "ALERTS", "RESEARCH", "RISK", "CODE"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFeedFilter(f)}
                    className={`rounded px-1.5 py-0.5 uppercase tracking-widest transition-colors ${
                      feedFilter === f ? "bg-foreground text-background" : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {feed.length === 0 && (
                <p className="p-3 font-mono text-[11px] text-muted-foreground">
                  No {feedFilter === "ALL" ? "" : feedFilter.toLowerCase() + " "}events.
                </p>
              )}
              {feed.map((e, i) => {
                const time = e.created_at ? new Date(e.created_at).toLocaleTimeString() : "";
                return (
                  <div key={`${e.agent}-${i}`} className="border-b border-border/70 px-3 py-2 last:border-b-0">
                    <div className="flex items-center justify-between font-mono text-[9px] uppercase text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Bot className="h-2.5 w-2.5" />
                        {agentTag(e.agent)}
                      </span>
                      <span>{time}</span>
                    </div>
                    <p className="mt-1 font-mono text-[11px] text-foreground">{e.message}</p>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Market alerts */}
          <section className="rounded border border-border">
            <div className="border-b border-border p-3 pb-2">
              <SectionLabel>Market Alerts</SectionLabel>
            </div>
            <ul>
              {marketAlerts.map((a) => (
                <li key={a.id} className="border-b border-border/70 px-3 py-2 last:border-b-0">
                  <div className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                    <FileText className="h-2.5 w-2.5" />
                    {a.source}
                  </div>
                  <p className="mt-1 font-mono text-[11px] text-foreground">{a.message}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {a.impacts.map((s) => (
                      <span key={s} className="rounded border border-border px-1 font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
                        {s}
                      </span>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {/* Strategy detail: Live Position + Parameters */}
          <section className="rounded border border-border">
            <div className="border-b border-border p-3 pb-2">
              <SectionLabel
                right={
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                    {selected.name}
                  </span>
                }
              >
                Strategy Detail
              </SectionLabel>
            </div>
            <div className="border-b border-border p-3">
              <p className="text-[9px] font-semibold uppercase tracking-widest text-muted-foreground">Live Position</p>
              <ul className="mt-2 space-y-1.5 font-mono text-[11px]">
                <li className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Allocation</span>
                  <span className="text-foreground">
                    {selected.allocationPct > 0 ? `${selected.allocationPct}% NAV` : "Not live"}
                  </span>
                </li>
                <li className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Qty</span>
                  <span className="text-foreground">{livePosition ? livePosition.qty.toLocaleString() : "—"}</span>
                </li>
                <li className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Entry</span>
                  <span className="text-foreground">{livePosition ? livePosition.avg_entry_price.toFixed(2) : "—"}</span>
                </li>
                <li className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Unrealized</span>
                  <span className="text-foreground">{livePosition ? signedMoney(livePosition.unrealized_pnl) : "—"}</span>
                </li>
                <li className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Exposure</span>
                  <span className="text-foreground">{livePosition ? wholeMoney(Math.abs(livePosition.market_value)) : "—"}</span>
                </li>
              </ul>
            </div>
            {liveDetail && (
              <div className="border-b border-border p-3">
                <p className="text-[9px] font-semibold uppercase tracking-widest text-muted-foreground">Hypothesis</p>
                <p className="mt-2 font-mono text-[11px] text-foreground">
                  {liveDetail.hypothesis ?? "—"}
                </p>
                <p className="mt-3 text-[9px] font-semibold uppercase tracking-widest text-muted-foreground">Risk Review</p>
                <p className="mt-1 font-mono text-[11px] text-foreground">
                  Status: {liveDetail.risk_status ?? "—"}
                </p>
                {liveDetail.risk_flags && liveDetail.risk_flags.length > 0 ? (
                  <ul className="mt-1 list-disc pl-4 font-mono text-[10px] text-foreground">
                    {liveDetail.risk_flags.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">No flags raised.</p>
                )}
              </div>
            )}
            <div className="p-3">
              <p className="text-[9px] font-semibold uppercase tracking-widest text-muted-foreground">Parameters</p>
              <ul className="mt-2 space-y-1.5 font-mono text-[11px]">
                {selected.params.map((p) => (
                  <li key={p.label} className="flex justify-between gap-3">
                    <span className="text-muted-foreground">{p.label}</span>
                    <span className="truncate text-right text-foreground">{p.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

function mapBackendStrategy(s: Record<string, unknown>): Strategy | null {
  const id = String(s.id ?? "");
  if (!id) return null;
  const tickers = (s.tickers as string[] | undefined) ?? [];
  const sharpe = Number(s.sharpe_ratio ?? 0);
  const recommendation = String(s.recommendation ?? "").toLowerCase();
  const status: StrategyStatus =
    recommendation === "rejected"
      ? "RISK"
      : recommendation === "ready_for_paper"
      ? "PAPER"
      : recommendation === "paper_trading"
      ? "PAPER"
      : recommendation === "researching" || recommendation === "building_data" || recommendation === "modeling"
      ? "RESEARCHING"
      : recommendation === "backtesting" || recommendation === "risk_review"
      ? "BACKTESTING"
      : recommendation === "warning"
      ? "BACKTESTING"
      : "PAPER";
  return {
    id,
    name: String(s.name ?? "STRATEGY"),
    sector: String(s.sector ?? "EQ"),
    ticker: tickers[0] ?? "—",
    status,
    dayPct: 0,
    weekPct: 0,
    mtdPct: 0,
    ytdPct: 0,
    sharpe,
    maxDD: 0,
    allocationPct: 0,
    params: [
      { label: "Universe", value: tickers.join(", ") || "—" },
      { label: "Signal", value: String((s as { backtest_results?: { signal_type?: string } }).backtest_results?.signal_type ?? "—") },
      { label: "Sharpe", value: sharpe.toFixed(2) },
      { label: "Status", value: String(s.recommendation ?? "—") },
    ],
    spark: [1, 1.01, 1.02, 1.01, 1.03, 1.04, 1.05, 1.04, 1.06, 1.07, 1.08, 1.09],
  };
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[9px] uppercase tracking-widest text-muted-foreground">{label}</p>
      <p className="mt-0.5 font-mono text-xs font-semibold text-foreground">{value}</p>
    </div>
  );
}

function StrategyPicker({
  strategies,
  selectedId,
  onSelect,
}: {
  strategies: Strategy[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const selected = strategies.find((s) => s.id === selectedId) ?? strategies[0];

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded border border-border bg-background px-2 py-1 font-mono text-xs font-semibold text-foreground transition-colors hover:bg-accent/60"
      >
        {selected.name}
        <ChevronDown className="h-3 w-3 text-muted-foreground" />
      </button>
      {open && (
        <ul className="absolute left-0 top-full z-20 mt-1 w-72 overflow-hidden rounded border border-border bg-card shadow-lg">
          {strategies.map((s) => {
            const active = s.id === selectedId;
            return (
              <li key={s.id}>
                <button
                  onClick={() => {
                    onSelect(s.id);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center justify-between gap-3 border-b border-border/70 px-3 py-2 text-left transition-colors hover:bg-accent/60 last:border-b-0 ${
                    active ? "bg-accent/40" : ""
                  }`}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[11px] font-semibold text-foreground">{s.name}</span>
                      <StatusBadge status={s.status} />
                    </div>
                    <div className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                      {s.sector} · 1D {pct(s.dayPct, 2)} · 1W {pct(s.weekPct, 2)}
                    </div>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
