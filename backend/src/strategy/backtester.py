"""Simple backtesting framework for strategy validation."""

from typing import Optional
from datetime import datetime
import numpy as np
import pandas as pd

from src.ingestion.market_data import MarketDataClient


class SimpleBacktester:
    """Backtests trading signals against historical data."""

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital
        self.market_client = MarketDataClient()

    def backtest_signal(
        self,
        ticker: str,
        signal: str,
        entry_date: Optional[str] = None,
        hold_days: int = 30,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.15,
    ) -> dict:
        """Backtest a single buy/sell signal."""
        df = self.market_client.get_ohlcv(ticker, period="2y")
        if df.empty:
            return {"error": f"No data for {ticker}"}

        if entry_date:
            entry_idx = df.index.searchsorted(pd.to_datetime(entry_date))
        else:
            entry_idx = len(df) - hold_days - 1

        if entry_idx >= len(df) - 1:
            return {"error": "Entry date too recent for backtesting"}

        entry_price = df.iloc[entry_idx]["Close"]
        direction = 1 if signal.lower() in ("buy", "strong buy") else -1

        trades = []
        position_open = True
        exit_idx = entry_idx
        exit_reason = "hold_period"

        for i in range(entry_idx + 1, min(entry_idx + hold_days + 1, len(df))):
            current_price = df.iloc[i]["Close"]
            pnl_pct = direction * (current_price - entry_price) / entry_price

            if pnl_pct <= -stop_loss_pct:
                exit_idx = i
                exit_reason = "stop_loss"
                break
            elif pnl_pct >= take_profit_pct:
                exit_idx = i
                exit_reason = "take_profit"
                break
            exit_idx = i

        exit_price = df.iloc[exit_idx]["Close"]
        pnl = direction * (exit_price - entry_price)
        pnl_pct = direction * (exit_price - entry_price) / entry_price
        hold_period = exit_idx - entry_idx

        return {
            "ticker": ticker.upper(),
            "signal": signal,
            "entry_date": str(df.index[entry_idx].date()),
            "entry_price": round(entry_price, 2),
            "exit_date": str(df.index[exit_idx].date()),
            "exit_price": round(exit_price, 2),
            "exit_reason": exit_reason,
            "pnl_per_share": round(pnl, 2),
            "pnl_pct": round(pnl_pct * 100, 2),
            "hold_days": hold_period,
        }

    def backtest_strategy(
        self,
        ticker: str,
        signals: list[dict],
    ) -> dict:
        """Backtest a series of signals and compute aggregate metrics."""
        results = []
        for signal_info in signals:
            result = self.backtest_signal(
                ticker=ticker,
                signal=signal_info.get("signal", "buy"),
                entry_date=signal_info.get("date"),
                hold_days=signal_info.get("hold_days", 30),
            )
            if "error" not in result:
                results.append(result)

        if not results:
            return {"error": "No valid backtest results"}

        pnl_pcts = [r["pnl_pct"] for r in results]
        wins = [p for p in pnl_pcts if p > 0]
        losses = [p for p in pnl_pcts if p <= 0]

        avg_return = np.mean(pnl_pcts)
        win_rate = len(wins) / len(pnl_pcts) if pnl_pcts else 0

        # Simplified Sharpe
        if len(pnl_pcts) > 1:
            sharpe = np.mean(pnl_pcts) / np.std(pnl_pcts) if np.std(pnl_pcts) > 0 else 0
        else:
            sharpe = 0

        return {
            "ticker": ticker.upper(),
            "total_trades": len(results),
            "win_rate": round(win_rate * 100, 1),
            "avg_return_pct": round(avg_return, 2),
            "total_return_pct": round(sum(pnl_pcts), 2),
            "best_trade_pct": round(max(pnl_pcts), 2) if pnl_pcts else 0,
            "worst_trade_pct": round(min(pnl_pcts), 2) if pnl_pcts else 0,
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown_pct": round(min(pnl_pcts), 2) if pnl_pcts else 0,
            "trades": results,
        }
