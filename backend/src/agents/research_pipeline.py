"""Research pipeline for /api/command.

Runs the full vertical slice: parse → data → research → features → backtest → risk → persist.
Each step emits an AgentLog row that the UI shows in the Agent Activity feed.

Deterministic by default; optional LLM enhancement via Anthropic key if present.
"""

from __future__ import annotations

import re
import time
import asyncio
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import AgentLog, Strategy, TradeOrder, TradingAccount
from src.ingestion.market_data import MarketDataClient
from src.agents.llm_enhance import enhance_hypothesis
from sqlalchemy import select as _sa_select
from config.settings import get_settings as _get_settings


# In-memory job registry for status polling. Wipes on restart — acceptable for MVP.
JOBS: dict[str, dict] = {}


STRATEGY_TEMPLATES = {
    "momentum": {
        "name": "MOM",
        "hypothesis": "Stocks with stronger recent momentum will outperform over the next holding period.",
        "lookback_days": 20,
        "rebalance": "daily",
    },
    "mean_reversion": {
        "name": "REV",
        "hypothesis": "Stocks that have deviated significantly from their moving average will revert.",
        "lookback_days": 20,
        "rebalance": "daily",
    },
    "volatility_breakout": {
        "name": "VOL-BO",
        "hypothesis": "Stocks breaking out of compressed volatility regimes continue trending.",
        "lookback_days": 20,
        "rebalance": "daily",
    },
}

DEFAULT_UNIVERSE = ["AAPL", "MSFT", "NVDA", "TSLA"]

# Status taxonomy emitted by the pipeline. Frontend renders these as badges.
STATUSES = (
    "queued",
    "researching",
    "building_data",
    "modeling",
    "backtesting",
    "risk_review",
    "ready_for_paper",
    "paper_trading",
    "completed",
    "rejected",
    "failed",
)


def _set_status(job_id: str, status: str):
    if job_id in JOBS:
        JOBS[job_id]["status"] = status

TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
STOP_WORDS = {
    "A", "AN", "THE", "FOR", "AND", "OR", "ON", "IN", "OF", "TO", "AT", "BY",
    "OVER", "WITH", "FROM", "RUN", "UP", "ETF", "US", "USA", "UK", "IS", "IT",
    "AS", "BE", "DO", "ARE", "I", "ME", "WE", "MY", "OUR", "NEW", "AI",
    "BUILD", "MAKE", "USE", "USING", "RESEARCH", "STRATEGY", "BACKTEST", "AGENT",
    "MOMENTUM", "MEAN", "REVERSION", "VOLATILITY", "BREAKOUT", "VOL",
    "LAST", "YEAR", "YEARS", "MONTH", "MONTHS", "DAY", "DAYS", "WEEK", "WEEKS",
    "PAST", "RECENT", "DAILY", "WEEKLY", "MONTHLY",
}


def parse_command(command: str) -> dict:
    """Extract tickers + strategy type from a free-text command."""
    cmd_lower = command.lower()

    if "mean reversion" in cmd_lower or "mean-reversion" in cmd_lower or "reversion" in cmd_lower:
        signal_type = "mean_reversion"
    elif "vol breakout" in cmd_lower or "volatility" in cmd_lower or "breakout" in cmd_lower:
        signal_type = "volatility_breakout"
    else:
        signal_type = "momentum"

    candidates = TICKER_RE.findall(command.upper())
    tickers = [t for t in candidates if t not in STOP_WORDS]
    # Dedupe preserving order
    seen = set()
    universe = []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            universe.append(t)
    if not universe:
        universe = list(DEFAULT_UNIVERSE)

    years = 2
    m = re.search(r"(\d+)\s*year", cmd_lower)
    if m:
        years = max(1, min(int(m.group(1)), 5))

    return {
        "signal_type": signal_type,
        "universe": universe[:10],
        "years": years,
    }


def _signal_series(df: pd.DataFrame, signal_type: str, lookback: int) -> pd.Series:
    close = df["Close"]
    if signal_type == "momentum":
        return close.pct_change(lookback)
    if signal_type == "mean_reversion":
        ma = close.rolling(lookback).mean()
        std = close.rolling(lookback).std()
        z = (close - ma) / std.replace(0, np.nan)
        return -z
    # volatility_breakout: today's range vs rolling avg range, scaled by sign of recent return
    rets = close.pct_change()
    vol = rets.rolling(lookback).std()
    recent_ret = close.pct_change(5)
    return np.sign(recent_ret) * (rets.abs() / vol.replace(0, np.nan))


def run_backtest(
    prices: dict[str, pd.DataFrame],
    signal_type: str,
    lookback: int = 20,
    top_n: int = 2,
    cost_bps: float = 5.0,
) -> dict:
    """Equal-weight long top-N daily-rebalanced backtest across the universe."""
    tickers = list(prices.keys())
    closes = pd.DataFrame({t: prices[t]["Close"] for t in tickers}).dropna(how="all")
    closes = closes.ffill().dropna()
    if len(closes) < lookback + 10:
        return {"error": "Insufficient history for backtest"}

    signals = pd.DataFrame(
        {t: _signal_series(prices[t].reindex(closes.index).ffill(), signal_type, lookback) for t in tickers},
        index=closes.index,
    )
    rets = closes.pct_change().fillna(0.0)

    # Rank each row; top_n highest get weight 1/top_n, others 0.
    weights = pd.DataFrame(0.0, index=closes.index, columns=tickers)
    ranks = signals.rank(axis=1, ascending=False)
    top_mask = ranks <= top_n
    weights = top_mask.astype(float).div(top_n)
    # Apply yesterday's weights to today's returns (no lookahead).
    weights_shifted = weights.shift(1).fillna(0.0)

    gross_daily = (weights_shifted * rets).sum(axis=1)
    # Transaction cost from turnover.
    turnover_daily = (weights_shifted - weights_shifted.shift(1).fillna(0.0)).abs().sum(axis=1)
    cost_daily = turnover_daily * (cost_bps / 10_000.0)
    daily_ret = gross_daily - cost_daily

    # Trim warmup period.
    daily_ret = daily_ret.iloc[lookback:]
    equity = (1.0 + daily_ret).cumprod()

    ann_factor = 252.0
    mean_d = daily_ret.mean()
    std_d = daily_ret.std()
    ann_return = (1 + mean_d) ** ann_factor - 1 if not np.isnan(mean_d) else 0.0
    ann_vol = std_d * np.sqrt(ann_factor) if std_d and not np.isnan(std_d) else 0.0
    sharpe = (mean_d / std_d) * np.sqrt(ann_factor) if std_d and std_d > 0 else 0.0
    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    max_dd = float(dd.min()) if len(dd) else 0.0
    win_rate = float((daily_ret > 0).mean()) if len(daily_ret) else 0.0
    avg_turnover = float(turnover_daily.mean()) if len(turnover_daily) else 0.0
    cum_return = float(equity.iloc[-1] - 1.0) if len(equity) else 0.0

    equity_curve = [
        {"date": d.strftime("%Y-%m-%d"), "equity": round(float(v), 4)}
        for d, v in equity.items()
    ]
    # Down-sample if too long.
    if len(equity_curve) > 500:
        step = len(equity_curve) // 500
        equity_curve = equity_curve[::step]

    return {
        "cumulative_return": round(cum_return * 100, 2),
        "annualized_return": round(float(ann_return) * 100, 2),
        "annualized_volatility": round(float(ann_vol) * 100, 2),
        "sharpe_ratio": round(float(sharpe), 3),
        "max_drawdown": round(max_dd * 100, 2),
        "win_rate": round(win_rate * 100, 1),
        "avg_turnover": round(avg_turnover, 3),
        "trading_days": int(len(daily_ret)),
        "equity_curve": equity_curve,
    }


def assess_risk(backtest: dict, universe: list[str]) -> dict:
    flags: list[str] = []
    if "error" in backtest:
        return {"risk_status": "rejected", "risk_flags": ["insufficient_data"]}

    if backtest["max_drawdown"] < -25.0:
        flags.append(f"max_drawdown_exceeded ({backtest['max_drawdown']}%)")
    if backtest["annualized_volatility"] > 50.0:
        flags.append(f"high_volatility ({backtest['annualized_volatility']}%)")
    if backtest["sharpe_ratio"] < 0:
        flags.append(f"negative_sharpe ({backtest['sharpe_ratio']})")
    if backtest["sharpe_ratio"] > 3.5:
        flags.append(f"suspicious_sharpe ({backtest['sharpe_ratio']})")
    if backtest["avg_turnover"] > 1.0:
        flags.append(f"high_turnover ({backtest['avg_turnover']})")
    if len(universe) <= 2:
        flags.append("concentrated_universe")

    # Concentration: equal-weight top-N is naturally concentrated when N is small relative to universe.
    if len(universe) > 0:
        top_weight = 1.0 / max(1, min(2, len(universe) // 2 or 1))
        if top_weight > 0.5:
            flags.append(f"high_concentration (per_position={int(top_weight * 100)}%)")

    if "trading_days" in backtest and backtest["trading_days"] < 60:
        flags.append("short_sample_size")

    # Long drawdown duration check via the equity curve.
    curve = backtest.get("equity_curve") or []
    if len(curve) > 30:
        peak = curve[0]["equity"]
        max_underwater = 0
        underwater = 0
        for p in curve:
            if p["equity"] >= peak:
                peak = p["equity"]
                underwater = 0
            else:
                underwater += 1
                max_underwater = max(max_underwater, underwater)
        if max_underwater > len(curve) * 0.4:
            flags.append(f"prolonged_drawdown ({max_underwater}_bars)")

    if any(f.startswith(("max_drawdown_exceeded", "insufficient_data")) for f in flags):
        status = "rejected"
    elif flags:
        status = "warning"
    else:
        status = "approved"
    return {"risk_status": status, "risk_flags": flags}


async def simulate_paper_orders(
    db_factory,
    job_id: str,
    strategy_id,
    universe: list[str],
    prices: dict[str, pd.DataFrame],
    signal_type: str,
    lookback: int,
    risk_status: str,
):
    """Emit simulated paper orders for the latest signal. Honors dry_run + circuit breaker."""
    if risk_status == "rejected":
        async with db_factory() as db:
            await _log(db, job_id, "trading_agent", "completed",
                       "Paper trading skipped — strategy was rejected by risk review.")
        return []

    settings = _get_settings()
    # Honor kill switch / circuit breaker.
    async with db_factory() as db:
        acct = (await db.execute(_sa_select(TradingAccount).limit(1))).scalar_one_or_none()
        if acct is None:
            acct = TradingAccount()
            db.add(acct)
            await db.commit()
            await db.refresh(acct)
        if acct.circuit_breaker_tripped:
            await _log(db, job_id, "trading_agent", "completed",
                       "Paper trading skipped — kill switch / circuit breaker active.")
            return []
        equity = acct.equity

    # Rank latest signals; long top-N.
    closes = pd.DataFrame({t: prices[t]["Close"] for t in universe}).dropna(how="all").ffill().dropna()
    if closes.empty:
        return []
    signals = pd.DataFrame(
        {t: _signal_series(prices[t].reindex(closes.index).ffill(), signal_type, lookback) for t in universe},
        index=closes.index,
    )
    latest = signals.iloc[-1].dropna()
    if latest.empty:
        return []
    top_n = max(1, min(2, len(latest) // 2 or 1))
    longs = latest.sort_values(ascending=False).head(top_n).index.tolist()
    notional_each = (equity * 0.05) if equity > 0 else 5_000.0

    side_status = "DRY_RUN" if settings.trading_dry_run else "FILLED"
    written: list[str] = []
    async with db_factory() as db:
        for t in longs:
            price = float(closes[t].iloc[-1])
            qty = max(1.0, round(notional_each / price, 2)) if price > 0 else 0
            if qty <= 0:
                continue
            order = TradeOrder(
                strategy_id=strategy_id,
                ticker=t,
                side="BUY",
                qty=qty,
                order_type="MARKET",
                status=side_status,
                filled_qty=qty if side_status == "FILLED" else 0.0,
                avg_fill_price=price if side_status == "FILLED" else None,
                broker_order_id=f"PAPER-{job_id}-{t}",
                agent_rationale=f"Top-{top_n} {signal_type} signal · paper simulation",
            )
            db.add(order)
            written.append(t)
        await db.commit()
        if written:
            await _log(db, job_id, "trading_agent", "completed",
                       f"Simulated {side_status.lower()} orders: BUY {', '.join(written)} "
                       f"@ ~${round(notional_each, 0):,.0f} each.")
        else:
            await _log(db, job_id, "trading_agent", "completed",
                       "Paper trading produced no actionable orders.")
    return written


async def _log(db: AsyncSession, job_id: str, agent: str, status: str, message: str, latency_ms: int = 0):
    log = AgentLog(
        job_id=job_id,
        agent_name=agent,
        status=status,
        message=message,
        latency_ms=latency_ms,
    )
    db.add(log)
    await db.commit()


async def run_pipeline(db_factory, job_id: str, command: str):
    """Full pipeline. db_factory is an async_sessionmaker so each step gets its own session."""
    try:
        _set_status(job_id, "researching")

        parsed = parse_command(command)
        universe = parsed["universe"]
        signal_type = parsed["signal_type"]
        tmpl = STRATEGY_TEMPLATES[signal_type]

        async with db_factory() as db:
            await _log(db, job_id, "orchestrator", "completed",
                       f"Parsed command: {signal_type} on {', '.join(universe)} ({parsed['years']}y).")

        # Data step (blocking yfinance — run in thread).
        _set_status(job_id, "building_data")
        t0 = time.time()
        client = MarketDataClient()
        period = f"{parsed['years']}y"

        def _fetch():
            out: dict[str, pd.DataFrame] = {}
            for t in universe:
                try:
                    df = client.get_ohlcv(t, period=period)
                    if df is not None and not df.empty:
                        out[t] = df
                except Exception as e:
                    print(f"[research_pipeline] fetch failed for {t}: {e}")
            return out

        prices = await asyncio.to_thread(_fetch)
        latency = int((time.time() - t0) * 1000)
        loaded = sorted(prices.keys())
        async with db_factory() as db:
            if not loaded:
                await _log(db, job_id, "data_agent", "failed",
                           f"No market data returned for {', '.join(universe)}.", latency)
                JOBS[job_id].update({"status": "failed", "error": "No market data."})
                return
            await _log(db, job_id, "data_agent", "completed",
                       f"Loaded {parsed['years']}y of daily prices for {', '.join(loaded)} "
                       f"({min(len(d) for d in prices.values())} bars).", latency)

        # Research step
        async with db_factory() as db:
            await _log(db, job_id, "sector_researcher", "completed",
                       f"Selected {tmpl['lookback_days']}-day {signal_type.replace('_', ' ')} template.")

        # Feature/model step
        _set_status(job_id, "modeling")
        async with db_factory() as db:
            await _log(db, job_id, "technical_analyst", "completed",
                       f"Generated {signal_type} signals; ranked {len(loaded)} assets, top-2 long.")

        # Backtest
        _set_status(job_id, "backtesting")
        t0 = time.time()
        bt = await asyncio.to_thread(
            run_backtest, prices, signal_type, tmpl["lookback_days"], min(2, max(1, len(loaded) // 2)),
        )
        latency = int((time.time() - t0) * 1000)
        async with db_factory() as db:
            if "error" in bt:
                await _log(db, job_id, "fundamental_analyst", "failed", bt["error"], latency)
                JOBS[job_id].update({"status": "failed", "error": bt["error"]})
                return
            await _log(db, job_id, "fundamental_analyst", "completed",
                       f"Backtest complete: Sharpe {bt['sharpe_ratio']}, "
                       f"MaxDD {bt['max_drawdown']}%, AnnRet {bt['annualized_return']}%.",
                       latency)

        # Risk
        _set_status(job_id, "risk_review")
        risk = assess_risk(bt, loaded)
        async with db_factory() as db:
            msg = f"Risk review: {risk['risk_status']}"
            if risk["risk_flags"]:
                msg += f" — flags: {', '.join(risk['risk_flags'])}"
            await _log(db, job_id, "trading_agent", "completed", msg)

        # Persist Strategy
        _set_status(job_id, "rejected" if risk["risk_status"] == "rejected" else "ready_for_paper")
        enriched = await enhance_hypothesis(
            command, signal_type, loaded, tmpl["hypothesis"], bt,
        )
        if enriched and enriched != tmpl["hypothesis"]:
            async with db_factory() as db:
                await _log(db, job_id, "sector_researcher", "completed",
                           "LLM-enhanced hypothesis attached to strategy.")
        strategy_name = f"{tmpl['name']}-{signal_type.upper().split('_')[0]}-{'-'.join(loaded[:3])}"
        async with db_factory() as db:
            strat = Strategy(
                name=strategy_name,
                sector="EQ",
                tickers=loaded,
                recommendation="rejected" if risk["risk_status"] == "rejected" else "ready_for_paper",
                rationale=enriched,
                confidence=max(0.0, min(1.0, 0.5 + bt["sharpe_ratio"] / 4)),
                risk_assessment=", ".join(risk["risk_flags"]) or "no_flags",
                sharpe_ratio=bt["sharpe_ratio"],
                max_drawdown=bt["max_drawdown"],
                backtest_results={
                    **bt,
                    "signal_type": signal_type,
                    "lookback_days": tmpl["lookback_days"],
                    "universe": loaded,
                    "rebalance": tmpl["rebalance"],
                    "risk_status": risk["risk_status"],
                    "risk_flags": risk["risk_flags"],
                    "hypothesis": enriched,
                    "template_hypothesis": tmpl["hypothesis"],
                },
                agent_outputs={"command": command, "parsed": parsed},
            )
            db.add(strat)
            await db.commit()
            await db.refresh(strat)
            strategy_id = str(strat.id)
            await _log(db, job_id, "orchestrator", "completed",
                       f"Strategy {strategy_name} ready for paper trading review.")

        # Paper trade simulation step
        if risk["risk_status"] != "rejected":
            _set_status(job_id, "paper_trading")
        await simulate_paper_orders(
            db_factory, job_id, strat.id, loaded, prices,
            signal_type, tmpl["lookback_days"], risk["risk_status"],
        )

        final_status = "rejected" if risk["risk_status"] == "rejected" else "completed"
        JOBS[job_id].update({
            "status": final_status,
            "strategy_id": strategy_id,
            "strategy_name": strategy_name,
            "metrics": {
                "sharpe": bt["sharpe_ratio"],
                "max_drawdown": bt["max_drawdown"],
                "annualized_return": bt["annualized_return"],
            },
            "risk_status": risk["risk_status"],
        })
    except Exception as e:
        print(f"[research_pipeline] job {job_id} failed: {e}")
        try:
            async with db_factory() as db:
                await _log(db, job_id, "orchestrator", "failed", f"Pipeline error: {e}")
        except Exception:
            pass
        JOBS[job_id].update({"status": "failed", "error": str(e)})
