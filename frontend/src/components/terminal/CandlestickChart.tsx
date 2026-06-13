"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Maximize2, Minimize2, SlidersHorizontal } from "lucide-react";
import { marketApi, type MarketCandle } from "@/lib/api";

interface CandlestickChartProps {
  ticker: string;
}

type TimeframeId = "1H" | "4H" | "1D" | "5D" | "1M" | "3M" | "1Y" | "5Y";

type TimeframeSpec = {
  id: TimeframeId;
  period: string;
  interval: string;
  limit: number;
  /** Poll interval ms; 0 = no polling (bars too coarse to change intraday). */
  pollMs: number;
};

const TIMEFRAMES: TimeframeSpec[] = [
  { id: "1H", period: "1d", interval: "1m", limit: 80, pollMs: 10_000 },
  { id: "4H", period: "1d", interval: "5m", limit: 60, pollMs: 15_000 },
  { id: "1D", period: "5d", interval: "5m", limit: 400, pollMs: 30_000 },
  { id: "5D", period: "5d", interval: "15m", limit: 160, pollMs: 60_000 },
  { id: "1M", period: "1mo", interval: "1h", limit: 200, pollMs: 60_000 },
  { id: "3M", period: "3mo", interval: "1d", limit: 90, pollMs: 0 },
  { id: "1Y", period: "1y", interval: "1d", limit: 260, pollMs: 0 },
  { id: "5Y", period: "5y", interval: "1wk", limit: 260, pollMs: 0 },
];

const UP_FILL = "#e5e5e5";
const UP_STROKE = "#e5e5e5";
const DOWN_FILL = "#404040";
const DOWN_STROKE = "#808080";
const GRID = "rgba(255,255,255,0.05)";
const AXIS_TEXT = "rgba(255,255,255,0.45)";

// ─── Indicator definitions ────────────────────────────────────────────────
type IndicatorId =
  | "SMA20"
  | "SMA50"
  | "EMA12"
  | "EMA26"
  | "BB20"
  | "RSI14";

type IndicatorDef = {
  id: IndicatorId;
  label: string;
  /** Where the indicator renders: on the price plot or in its own oscillator panel. */
  pane: "price" | "osc";
};

const INDICATORS: IndicatorDef[] = [
  { id: "SMA20", label: "SMA 20", pane: "price" },
  { id: "SMA50", label: "SMA 50", pane: "price" },
  { id: "EMA12", label: "EMA 12", pane: "price" },
  { id: "EMA26", label: "EMA 26", pane: "price" },
  { id: "BB20", label: "Bollinger 20 · 2σ", pane: "price" },
  { id: "RSI14", label: "RSI 14", pane: "osc" },
];

// Greyscale styles per indicator
const INDICATOR_STYLE: Record<IndicatorId, { stroke: string; dash?: string; opacity?: number }> = {
  SMA20: { stroke: "#ffffff", dash: undefined },
  SMA50: { stroke: "#ffffff", dash: "4 3" },
  EMA12: { stroke: "#bdbdbd", dash: undefined },
  EMA26: { stroke: "#bdbdbd", dash: "4 3" },
  BB20: { stroke: "#888888", dash: undefined, opacity: 0.9 },
  RSI14: { stroke: "#e5e5e5" },
};

function computeSMA(values: number[], window: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  let sum = 0;
  for (let i = 0; i < values.length; i++) {
    sum += values[i];
    if (i >= window) sum -= values[i - window];
    if (i >= window - 1) out[i] = sum / window;
  }
  return out;
}

function computeEMA(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (values.length === 0) return out;
  const k = 2 / (period + 1);
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    if (i === period - 1) {
      // seed with SMA of first `period` values
      let s = 0;
      for (let j = 0; j < period; j++) s += values[j];
      prev = s / period;
      out[i] = prev;
    } else if (i >= period && prev != null) {
      prev = values[i] * k + prev * (1 - k);
      out[i] = prev;
    }
  }
  return out;
}

function computeBollinger(values: number[], window: number, mult: number) {
  const upper: (number | null)[] = new Array(values.length).fill(null);
  const middle: (number | null)[] = new Array(values.length).fill(null);
  const lower: (number | null)[] = new Array(values.length).fill(null);
  if (values.length < window) return { upper, middle, lower };
  for (let i = window - 1; i < values.length; i++) {
    let sum = 0;
    for (let j = i - window + 1; j <= i; j++) sum += values[j];
    const mean = sum / window;
    let varSum = 0;
    for (let j = i - window + 1; j <= i; j++) varSum += (values[j] - mean) ** 2;
    const sd = Math.sqrt(varSum / window);
    middle[i] = mean;
    upper[i] = mean + mult * sd;
    lower[i] = mean - mult * sd;
  }
  return { upper, middle, lower };
}

function computeRSI(values: number[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (values.length <= period) return out;
  let gain = 0;
  let loss = 0;
  for (let i = 1; i <= period; i++) {
    const ch = values[i] - values[i - 1];
    if (ch >= 0) gain += ch;
    else loss -= ch;
  }
  gain /= period;
  loss /= period;
  out[period] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let i = period + 1; i < values.length; i++) {
    const ch = values[i] - values[i - 1];
    const g = ch > 0 ? ch : 0;
    const l = ch < 0 ? -ch : 0;
    gain = (gain * (period - 1) + g) / period;
    loss = (loss * (period - 1) + l) / period;
    out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return out;
}

function buildPath(
  series: (number | null)[],
  xFor: (i: number) => number,
  yFor: (v: number) => number
): string {
  let d = "";
  let started = false;
  for (let i = 0; i < series.length; i++) {
    const v = series[i];
    if (v == null) {
      started = false;
      continue;
    }
    const cmd = started ? "L" : "M";
    d += `${cmd}${xFor(i)},${yFor(v)} `;
    started = true;
  }
  return d.trim();
}

function formatTime(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatDateTick(iso: string, intraday: boolean) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (!intraday) {
    return d.toLocaleString(undefined, { month: "short", day: "numeric", year: "2-digit" });
  }
  const h = d.getHours();
  if (h === 0 && d.getMinutes() === 0) {
    return d.toLocaleString(undefined, { month: "numeric", day: "numeric" });
  }
  return d.toLocaleString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
}

function compactVolume(n: number | null) {
  if (n == null || Number.isNaN(n)) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`;
  return n.toLocaleString();
}

export function CandlestickChart({ ticker }: CandlestickChartProps) {
  const [fullscreen, setFullscreen] = useState(false);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 360 });
  const [timeframeId, setTimeframeId] = useState<TimeframeId>("1D");
  const [candles, setCandles] = useState<MarketCandle[]>([]);
  const [loading, setLoading] = useState(false);

  const [enabled, setEnabled] = useState<Set<IndicatorId>>(new Set());
  const [indicatorsOpen, setIndicatorsOpen] = useState(false);
  const indicatorsRef = useRef<HTMLDivElement>(null);

  const timeframe = TIMEFRAMES.find((t) => t.id === timeframeId) ?? TIMEFRAMES[2];
  const intraday = !["1d", "1wk", "1mo"].includes(timeframe.interval);

  useEffect(() => {
    if (!indicatorsOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (indicatorsRef.current && !indicatorsRef.current.contains(e.target as Node)) {
        setIndicatorsOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [indicatorsOpen]);

  const toggleIndicator = (id: IndicatorId) => {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const load = () => {
      marketApi
        .getCandles(ticker, timeframe.period, timeframe.interval, timeframe.limit)
        .then((data) => {
          if (cancelled) return;
          setCandles(data.candles);
        })
        .catch(() => {})
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    };
    load();
    if (timeframe.pollMs > 0) {
      const t = window.setInterval(load, timeframe.pollMs);
      return () => {
        cancelled = true;
        window.clearInterval(t);
      };
    }
    return () => {
      cancelled = true;
    };
  }, [ticker, timeframe.period, timeframe.interval, timeframe.limit, timeframe.pollMs]);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const e = entries[0];
      if (e) setSize({ w: e.contentRect.width, h: e.contentRect.height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [fullscreen]);

  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  const last = candles.at(-1);
  const prevLast = candles.at(-2);
  const change = last && prevLast ? last.close - prevLast.close : 0;
  const changePct = last && prevLast ? (change / prevLast.close) * 100 : 0;
  const totalVol = candles.reduce((s, c) => s + (c.volume ?? 0), 0);

  const hovered = hoverIndex != null ? candles[hoverIndex] : null;

  // Indicator series
  const closes = useMemo(() => candles.map((c) => c.close), [candles]);
  const sma20 = useMemo(() => (enabled.has("SMA20") ? computeSMA(closes, 20) : null), [closes, enabled]);
  const sma50 = useMemo(() => (enabled.has("SMA50") ? computeSMA(closes, 50) : null), [closes, enabled]);
  const ema12 = useMemo(() => (enabled.has("EMA12") ? computeEMA(closes, 12) : null), [closes, enabled]);
  const ema26 = useMemo(() => (enabled.has("EMA26") ? computeEMA(closes, 26) : null), [closes, enabled]);
  const bb = useMemo(() => (enabled.has("BB20") ? computeBollinger(closes, 20, 2) : null), [closes, enabled]);
  const rsi = useMemo(() => (enabled.has("RSI14") ? computeRSI(closes, 14) : null), [closes, enabled]);

  const showOsc = enabled.has("RSI14");

  // Layout
  const pad = { top: 24, right: 70, bottom: 60, left: 12 };
  const volH = Math.max(50, Math.min(110, size.h * 0.18));
  const oscH = showOsc ? Math.max(70, Math.min(120, size.h * 0.18)) : 0;
  const oscGap = showOsc ? 6 : 0;
  const priceTop = pad.top;
  const priceBottom = size.h - pad.bottom - volH - oscH - oscGap - 8;
  const oscTop = priceBottom + 8;
  const oscBottom = oscTop + oscH;
  const volTop = size.h - pad.bottom - volH;
  const volBottom = size.h - pad.bottom;
  const plotLeft = pad.left;
  const plotRight = size.w - pad.right;
  const plotW = Math.max(1, plotRight - plotLeft);

  const lows = candles.map((c) => c.low);
  const highs = candles.map((c) => c.high);
  const hasData = candles.length > 1;
  let minLow = hasData ? Math.min(...lows) : 0;
  let maxHigh = hasData ? Math.max(...highs) : 1;
  // Expand price range so overlay indicators (BB upper/lower especially) stay in view
  for (const series of [sma20, sma50, ema12, ema26, bb?.upper, bb?.lower]) {
    if (!series) continue;
    for (const v of series) {
      if (v == null) continue;
      if (v < minLow) minLow = v;
      if (v > maxHigh) maxHigh = v;
    }
  }
  const range = Math.max(maxHigh - minLow, 1e-6);
  const yMin = minLow - range * 0.05;
  const yMax = maxHigh + range * 0.05;
  const maxVol = hasData ? Math.max(...candles.map((c) => c.volume ?? 0), 1) : 1;

  const step = plotW / Math.max(candles.length, 1);
  const candleW = Math.max(1.5, Math.min(14, step * 0.7));

  const xFor = (i: number) => plotLeft + step * i + step / 2;
  const yFor = (p: number) =>
    priceTop + ((yMax - p) / (yMax - yMin)) * (priceBottom - priceTop);
  const yVolFor = (v: number) => volBottom - (v / maxVol) * (volBottom - volTop);
  const yOscFor = (v: number) => oscTop + ((100 - v) / 100) * (oscBottom - oscTop);

  // Y ticks (~6)
  const yTicks = useMemo(() => {
    const out: number[] = [];
    const n = 7;
    for (let i = 0; i <= n; i++) {
      out.push(yMin + ((yMax - yMin) * i) / n);
    }
    return out;
  }, [yMin, yMax]);

  // X ticks (~6)
  const xTickIndices = useMemo(() => {
    if (candles.length === 0) return [];
    const n = Math.min(6, candles.length);
    const out: number[] = [];
    for (let i = 0; i < n; i++) {
      out.push(Math.floor((i * (candles.length - 1)) / Math.max(n - 1, 1)));
    }
    return out;
  }, [candles.length]);

  const handleMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!hasData) return;
    const svg = e.currentTarget;
    const ctm = svg.getScreenCTM();
    if (!ctm) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const local = pt.matrixTransform(ctm.inverse());
    const i = Math.max(
      0,
      Math.min(candles.length - 1, Math.floor((local.x - plotLeft) / step))
    );
    setHoverIndex(i);
  };

  const chart = (
    <div
      ref={wrapRef}
      className="relative h-full w-full bg-background"
    >
      {/* Header overlay */}
      <div className="pointer-events-none absolute left-3 top-2 z-10 font-mono text-[11px]">
        {last ? (
          <>
            <div className="text-foreground">
              <span className="text-muted-foreground">C</span>{" "}
              <span className="font-semibold">{last.close.toFixed(2)}</span>{" "}
              <span className={change >= 0 ? "text-foreground" : "text-muted-foreground"}>
                {change >= 0 ? "+" : ""}
                {change.toFixed(2)} ({changePct >= 0 ? "+" : ""}
                {changePct.toFixed(2)}%)
              </span>
            </div>
            <div className="mt-0.5 text-muted-foreground">VOL {compactVolume(totalVol)}</div>
          </>
        ) : (
          <div className="text-muted-foreground">
            {loading ? `Loading ${ticker}…` : "No data"}
          </div>
        )}
      </div>

      {/* Timeframe selector */}
      <div className="pointer-events-auto absolute right-2 top-2 z-10 flex items-center gap-1 rounded border border-border bg-background/80 p-0.5 font-mono text-[10px]">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.id}
            onClick={() => setTimeframeId(tf.id)}
            className={`rounded px-1.5 py-0.5 uppercase tracking-widest transition-colors ${
              tf.id === timeframeId
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {tf.id}
          </button>
        ))}
        {timeframe.pollMs > 0 && (
          <span className="ml-1 flex items-center gap-1 pl-1 pr-0.5 text-[9px] uppercase text-muted-foreground">
            <span className="h-1 w-1 rounded-full bg-green-500" />
            live
          </span>
        )}
      </div>

      {/* Indicators button + popover */}
      <div ref={indicatorsRef} className="absolute bottom-2 left-2 z-10">
        <button
          onClick={() => setIndicatorsOpen((v) => !v)}
          className="flex items-center gap-1.5 rounded border border-border bg-background/80 px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        >
          <SlidersHorizontal className="h-3 w-3" />
          Indicators
          {enabled.size > 0 && (
            <span className="rounded bg-foreground px-1 text-[9px] text-background">{enabled.size}</span>
          )}
        </button>
        {indicatorsOpen && (
          <div className="absolute bottom-full left-0 mb-1 w-56 rounded border border-border bg-card p-2 font-mono text-[11px] shadow-lg">
            <p className="mb-1.5 px-1 text-[9px] uppercase tracking-widest text-muted-foreground">Overlay</p>
            {INDICATORS.filter((ind) => ind.pane === "price").map((ind) => {
              const on = enabled.has(ind.id);
              return (
                <button
                  key={ind.id}
                  onClick={() => toggleIndicator(ind.id)}
                  className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-foreground transition-colors hover:bg-accent/60"
                >
                  <span
                    className="inline-flex h-3 w-3 items-center justify-center rounded border border-border text-[9px]"
                    style={{ background: on ? INDICATOR_STYLE[ind.id].stroke : "transparent" }}
                  >
                    {on && <span className="text-background">✓</span>}
                  </span>
                  {ind.label}
                </button>
              );
            })}
            <p className="mb-1.5 mt-2 px-1 text-[9px] uppercase tracking-widest text-muted-foreground">Oscillator</p>
            {INDICATORS.filter((ind) => ind.pane === "osc").map((ind) => {
              const on = enabled.has(ind.id);
              return (
                <button
                  key={ind.id}
                  onClick={() => toggleIndicator(ind.id)}
                  className="flex w-full items-center gap-2 rounded px-1 py-1 text-left text-foreground transition-colors hover:bg-accent/60"
                >
                  <span
                    className="inline-flex h-3 w-3 items-center justify-center rounded border border-border text-[9px]"
                    style={{ background: on ? INDICATOR_STYLE[ind.id].stroke : "transparent" }}
                  >
                    {on && <span className="text-background">✓</span>}
                  </span>
                  {ind.label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Fullscreen button */}
      <button
        onClick={() => setFullscreen((v) => !v)}
        className="absolute bottom-2 right-2 z-10 rounded border border-border bg-background/80 p-1 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
        aria-label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
      >
        {fullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
      </button>

      {/* SVG chart */}
      <svg
        width={size.w}
        height={size.h}
        className="block cursor-crosshair"
        onMouseMove={handleMove}
        onMouseLeave={() => setHoverIndex(null)}
      >
        {/* Horizontal grid + Y axis labels (right) */}
        {hasData &&
          yTicks.map((t) => {
            const y = yFor(t);
            return (
              <g key={t}>
                <line
                  x1={plotLeft}
                  x2={plotRight}
                  y1={y}
                  y2={y}
                  stroke={GRID}
                  strokeWidth={1}
                />
                <text
                  x={plotRight + 6}
                  y={y + 3}
                  fontFamily="inherit"
                  fontSize={10}
                  fill={AXIS_TEXT}
                >
                  {t.toFixed(2)}
                </text>
              </g>
            );
          })}

        {/* X axis labels (bottom) */}
        {hasData &&
          xTickIndices.map((i) => (
            <text
              key={i}
              x={xFor(i)}
              y={size.h - pad.bottom + 14}
              textAnchor="middle"
              fontFamily="inherit"
              fontSize={10}
              fill={AXIS_TEXT}
            >
              {formatDateTick(candles[i].time, intraday)}
            </text>
          ))}

        {/* Volume separator */}
        {hasData && (
          <line
            x1={plotLeft}
            x2={plotRight}
            y1={volTop - 4}
            y2={volTop - 4}
            stroke={GRID}
          />
        )}

        {/* Volume bars */}
        {hasData &&
          candles.map((c, i) => {
            const v = c.volume ?? 0;
            const h = volBottom - yVolFor(v);
            const up = c.close >= c.open;
            return (
              <rect
                key={`v-${c.time}-${i}`}
                x={xFor(i) - candleW / 2}
                y={yVolFor(v)}
                width={candleW}
                height={Math.max(1, h)}
                fill={up ? UP_FILL : DOWN_STROKE}
                opacity={0.55}
              />
            );
          })}

        {/* Candlesticks */}
        {hasData &&
          candles.map((c, i) => {
            const up = c.close >= c.open;
            const x = xFor(i);
            const yHigh = yFor(c.high);
            const yLow = yFor(c.low);
            const bodyTop = yFor(Math.max(c.open, c.close));
            const bodyBottom = yFor(Math.min(c.open, c.close));
            const bodyH = Math.max(1, bodyBottom - bodyTop);
            const fill = up ? UP_FILL : DOWN_FILL;
            const stroke = up ? UP_STROKE : DOWN_STROKE;
            return (
              <g key={`${c.time}-${i}`}>
                <line x1={x} x2={x} y1={yHigh} y2={yLow} stroke={stroke} strokeWidth={1} />
                <rect
                  x={x - candleW / 2}
                  y={bodyTop}
                  width={candleW}
                  height={bodyH}
                  fill={fill}
                  stroke={stroke}
                  strokeWidth={1}
                />
              </g>
            );
          })}

        {/* Bollinger band fill */}
        {hasData && bb && (
          <path
            d={(() => {
              // upper line forward, lower line reverse
              let d = "";
              let started = false;
              for (let i = 0; i < bb.upper.length; i++) {
                const v = bb.upper[i];
                if (v == null) continue;
                d += `${started ? "L" : "M"}${xFor(i)},${yFor(v)} `;
                started = true;
              }
              for (let i = bb.lower.length - 1; i >= 0; i--) {
                const v = bb.lower[i];
                if (v == null) continue;
                d += `L${xFor(i)},${yFor(v)} `;
              }
              return d + "Z";
            })()}
            fill="rgba(255,255,255,0.05)"
            stroke="none"
          />
        )}

        {/* Indicator overlays */}
        {hasData && sma20 && (
          <path d={buildPath(sma20, xFor, yFor)} fill="none" stroke={INDICATOR_STYLE.SMA20.stroke} strokeWidth={1.25} strokeDasharray={INDICATOR_STYLE.SMA20.dash} />
        )}
        {hasData && sma50 && (
          <path d={buildPath(sma50, xFor, yFor)} fill="none" stroke={INDICATOR_STYLE.SMA50.stroke} strokeWidth={1.25} strokeDasharray={INDICATOR_STYLE.SMA50.dash} />
        )}
        {hasData && ema12 && (
          <path d={buildPath(ema12, xFor, yFor)} fill="none" stroke={INDICATOR_STYLE.EMA12.stroke} strokeWidth={1} strokeDasharray={INDICATOR_STYLE.EMA12.dash} />
        )}
        {hasData && ema26 && (
          <path d={buildPath(ema26, xFor, yFor)} fill="none" stroke={INDICATOR_STYLE.EMA26.stroke} strokeWidth={1} strokeDasharray={INDICATOR_STYLE.EMA26.dash} />
        )}
        {hasData && bb && (
          <>
            <path d={buildPath(bb.upper, xFor, yFor)} fill="none" stroke={INDICATOR_STYLE.BB20.stroke} strokeWidth={1} opacity={INDICATOR_STYLE.BB20.opacity} />
            <path d={buildPath(bb.middle, xFor, yFor)} fill="none" stroke={INDICATOR_STYLE.BB20.stroke} strokeWidth={0.75} strokeDasharray="3 3" opacity={INDICATOR_STYLE.BB20.opacity} />
            <path d={buildPath(bb.lower, xFor, yFor)} fill="none" stroke={INDICATOR_STYLE.BB20.stroke} strokeWidth={1} opacity={INDICATOR_STYLE.BB20.opacity} />
          </>
        )}

        {/* RSI oscillator panel */}
        {hasData && showOsc && rsi && (
          <g>
            <line x1={plotLeft} x2={plotRight} y1={oscTop - 4} y2={oscTop - 4} stroke={GRID} />
            {[30, 50, 70].map((lvl) => (
              <g key={lvl}>
                <line
                  x1={plotLeft}
                  x2={plotRight}
                  y1={yOscFor(lvl)}
                  y2={yOscFor(lvl)}
                  stroke="rgba(255,255,255,0.08)"
                  strokeDasharray={lvl === 50 ? "1 3" : undefined}
                />
                <text
                  x={plotRight + 6}
                  y={yOscFor(lvl) + 3}
                  fontFamily="inherit"
                  fontSize={9}
                  fill={AXIS_TEXT}
                >
                  {lvl}
                </text>
              </g>
            ))}
            <text
              x={plotLeft + 4}
              y={oscTop + 10}
              fontFamily="inherit"
              fontSize={9}
              fill={AXIS_TEXT}
            >
              RSI 14
              {rsi.at(-1) != null && (
                <tspan dx={6} fill="#e5e5e5" fontWeight={600}>
                  {(rsi.at(-1) as number).toFixed(1)}
                </tspan>
              )}
            </text>
            <path d={buildPath(rsi, xFor, yOscFor)} fill="none" stroke={INDICATOR_STYLE.RSI14.stroke} strokeWidth={1} />
          </g>
        )}

        {/* Current price line + pill on right */}
        {last && (
          <g>
            <line
              x1={plotLeft}
              x2={plotRight}
              y1={yFor(last.close)}
              y2={yFor(last.close)}
              stroke="rgba(255,255,255,0.35)"
              strokeDasharray="2 3"
              strokeWidth={1}
            />
            <rect
              x={plotRight + 2}
              y={yFor(last.close) - 9}
              width={56}
              height={18}
              fill={UP_FILL}
            />
            <text
              x={plotRight + 30}
              y={yFor(last.close) + 4}
              textAnchor="middle"
              fontFamily="inherit"
              fontSize={11}
              fontWeight={600}
              fill="#000"
            >
              {last.close.toFixed(2)}
            </text>
          </g>
        )}

        {/* Crosshair */}
        {hovered && hoverIndex != null && (
          <g pointerEvents="none">
            <line
              x1={xFor(hoverIndex)}
              x2={xFor(hoverIndex)}
              y1={priceTop}
              y2={volBottom}
              stroke="rgba(255,255,255,0.35)"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
            <line
              x1={plotLeft}
              x2={plotRight}
              y1={yFor(hovered.close)}
              y2={yFor(hovered.close)}
              stroke="rgba(255,255,255,0.35)"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
            {/* Tooltip box */}
            {(() => {
              const x = xFor(hoverIndex);
              const boxW = 184;
              const boxH = 96;
              const flip = x > plotRight - boxW - 20;
              const boxX = flip ? x - boxW - 10 : x + 10;
              const boxY = priceTop + 8;
              return (
                <g>
                  <rect
                    x={boxX}
                    y={boxY}
                    width={boxW}
                    height={boxH}
                    fill="#0a0a0a"
                    stroke="rgba(255,255,255,0.2)"
                  />
                  <text
                    x={boxX + 10}
                    y={boxY + 18}
                    fontFamily="inherit"
                    fontSize={10}
                    fill={AXIS_TEXT}
                  >
                    {formatTime(hovered.time)}
                  </text>
                  {[
                    `O ${hovered.open.toFixed(2)}   H ${hovered.high.toFixed(2)}`,
                    `L ${hovered.low.toFixed(2)}   C ${hovered.close.toFixed(2)}`,
                    `V ${compactVolume(hovered.volume)}`,
                  ].map((line, j) => (
                    <text
                      key={line}
                      x={boxX + 10}
                      y={boxY + 38 + j * 16}
                      fontFamily="inherit"
                      fontSize={11}
                      fill="#e5e5e5"
                    >
                      {line}
                    </text>
                  ))}
                </g>
              );
            })()}
          </g>
        )}
      </svg>
    </div>
  );

  if (fullscreen) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col bg-background">
        <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-2">
          <div className="font-mono text-xs">
            <span className="font-semibold text-foreground">{ticker}</span>
            <span className="ml-3 text-muted-foreground">candles · {candles.length} bars</span>
          </div>
          <button
            onClick={() => setFullscreen(false)}
            className="rounded border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            Esc · Exit
          </button>
        </div>
        <div className="min-h-0 flex-1">{chart}</div>
      </div>
    );
  }

  return chart;
}
