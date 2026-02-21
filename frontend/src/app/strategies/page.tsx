"use client";

import { useState, useEffect } from "react";
import { strategiesApi } from "@/lib/api";
import { getSignalColor, formatDate } from "@/lib/utils";
import { TrendingUp, Loader2 } from "lucide-react";

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStrategies();
  }, []);

  async function loadStrategies() {
    try {
      const res = await strategiesApi.list();
      setStrategies(res.strategies);
    } catch {
      setStrategies([]);
    }
    setLoading(false);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Trading Strategies</h1>
        <p className="text-sm text-muted-foreground">
          AI-generated strategies from multi-agent research synthesis
        </p>
      </div>

      {strategies.length === 0 ? (
        <div className="py-12 text-center">
          <TrendingUp className="mx-auto h-12 w-12 text-muted-foreground/40" />
          <h3 className="mt-4 text-lg font-medium">No strategies yet</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Run research on companies to generate strategy recommendations
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {strategies.map((s) => (
            <div
              key={s.id as string}
              className="rounded-xl border border-border bg-card p-6 transition-all hover:border-primary/50"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold">{s.name as string}</h3>
                  <p className="text-sm text-muted-foreground">
                    {((s.tickers as string[]) || []).join(", ")} &middot; {s.sector as string}
                  </p>
                </div>
                <div className="text-right">
                  <span className={`text-lg font-bold ${getSignalColor(s.recommendation as string)}`}>
                    {s.recommendation as string}
                  </span>
                  {s.confidence != null && (
                    <p className="text-xs text-muted-foreground">
                      Confidence: {s.confidence as number}%
                    </p>
                  )}
                </div>
              </div>

              <div className="mt-4 grid grid-cols-4 gap-4 bg-muted/20 p-4 rounded-lg">
                <div>
                  <p className="text-xs text-muted-foreground">Sharpe Ratio</p>
                  <p className="font-medium text-blue-400">
                    {s.sharpe_ratio != null ? (s.sharpe_ratio as number).toFixed(2) : "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Max Drawdown</p>
                  <p className="font-medium text-red-400">
                    {s.max_drawdown != null ? `${(s.max_drawdown as number).toFixed(2)}%` : "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Win Rate</p>
                  <p className="font-medium text-green-400">
                    {s.backtest_results && (s.backtest_results as any).win_rate_pct != null
                      ? `${(s.backtest_results as any).win_rate_pct}%`
                      : "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Created</p>
                  <p className="font-medium">{formatDate(s.created_at as string)}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
