"""Seed a demo strategy + activity feed so a fresh install shows something useful.

Run:
    cd backend && .venv/bin/python scripts/seed_demo.py
"""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from src.database.connection import engine, Base, async_session
from src.database.models import AgentLog, Strategy, TradeOrder
from src.agents.research_pipeline import (
    STRATEGY_TEMPLATES, run_backtest, assess_risk,
)
from sqlalchemy import select


DEMO_TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA"]
DEMO_JOB_ID = "seed-demo"
DEMO_NAME = "MOM-MOMENTUM-AAPL-MSFT-NVDA"


def _synthetic_prices(n: int = 420) -> dict[str, pd.DataFrame]:
    np.random.seed(42)
    idx = pd.date_range("2023-01-03", periods=n, freq="B")
    out = {}
    for ticker in DEMO_TICKERS:
        # Per-name drift so the picks differentiate.
        drift = 0.0004 + (hash(ticker) % 5) * 0.00002
        rets = np.random.randn(n) * 0.016 + drift
        close = 100 * np.exp(np.cumsum(rets))
        out[ticker] = pd.DataFrame({"Close": close}, index=idx)
    return out


async def seed():
    # Ensure tables exist (safe to run repeatedly).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as db:
        existing = (
            await db.execute(select(Strategy).where(Strategy.name == DEMO_NAME))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"Demo strategy '{DEMO_NAME}' already exists ({existing.id}); skipping.")
            await engine.dispose()
            return

        prices = _synthetic_prices()
        tmpl = STRATEGY_TEMPLATES["momentum"]
        bt = run_backtest(prices, "momentum", tmpl["lookback_days"], top_n=2)
        risk = assess_risk(bt, DEMO_TICKERS)

        strat = Strategy(
            name=DEMO_NAME,
            sector="EQ",
            tickers=DEMO_TICKERS,
            recommendation="ready_for_paper",
            rationale=tmpl["hypothesis"],
            confidence=max(0.0, min(1.0, 0.5 + bt["sharpe_ratio"] / 4)),
            risk_assessment=", ".join(risk["risk_flags"]) or "no_flags",
            sharpe_ratio=bt["sharpe_ratio"],
            max_drawdown=bt["max_drawdown"],
            backtest_results={
                **bt,
                "signal_type": "momentum",
                "lookback_days": tmpl["lookback_days"],
                "universe": DEMO_TICKERS,
                "rebalance": tmpl["rebalance"],
                "risk_status": risk["risk_status"],
                "risk_flags": risk["risk_flags"],
                "hypothesis": tmpl["hypothesis"],
            },
            agent_outputs={"seed": True, "command": "demo: momentum on AAPL/MSFT/NVDA/TSLA"},
        )
        db.add(strat)
        await db.commit()
        await db.refresh(strat)

        # A small activity history.
        for agent, msg in [
            ("orchestrator", f"Parsed command: momentum on {', '.join(DEMO_TICKERS)} (2y)."),
            ("data_agent", f"Loaded 2y of daily prices for {', '.join(DEMO_TICKERS)} (synthetic seed)."),
            ("sector_researcher", "Selected 20-day momentum template."),
            ("technical_analyst", "Generated momentum signals; ranked 4 assets, top-2 long."),
            ("fundamental_analyst",
                f"Backtest complete: Sharpe {bt['sharpe_ratio']}, MaxDD {bt['max_drawdown']}%, "
                f"AnnRet {bt['annualized_return']}%."),
            ("trading_agent",
                f"Risk review: {risk['risk_status']}" +
                (f" — flags: {', '.join(risk['risk_flags'])}" if risk['risk_flags'] else "")),
            ("orchestrator", f"Strategy {DEMO_NAME} ready for paper trading review."),
        ]:
            db.add(AgentLog(
                job_id=DEMO_JOB_ID, agent_name=agent, status="completed", message=msg,
            ))

        # Two simulated paper orders.
        closes = pd.DataFrame({t: prices[t]["Close"] for t in DEMO_TICKERS}).iloc[-1]
        for ticker in DEMO_TICKERS[:2]:
            price = float(closes[ticker])
            qty = round(5_000 / price, 2)
            db.add(TradeOrder(
                strategy_id=strat.id,
                ticker=ticker,
                side="BUY",
                qty=qty,
                order_type="MARKET",
                status="DRY_RUN",
                filled_qty=0.0,
                avg_fill_price=None,
                broker_order_id=f"PAPER-{DEMO_JOB_ID}-{ticker}",
                agent_rationale="Seeded demo order (dry-run)",
            ))
        await db.commit()
        print(f"Seeded demo strategy '{DEMO_NAME}' (id={strat.id}).")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
